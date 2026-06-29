"""LangGraph 自愈状态机：把 generate_sql / execute_sql / reflect_and_rewrite
三个节点连成一条「生成 → 执行 → 反思重写」的自愈流水线。

拓扑::

    START → generate_sql → execute_sql → should_retry
    should_retry routes:
      "retry"  → reflect_and_rewrite → execute_sql   (heal loop)
      "human"  → END                                  (destructive, awaiting approval)
      "end"    → END                                  (success or max retries)

路由函数 ``should_retry`` 三态优先级：

1. **``"human"``** —— 高危语句且未获人工审批（``is_destructive`` 且 ``not approved``）。
   ``execute_sql`` 的安全围栏会跳过执行，流程在此直接收尾等待人工介入，
   避免未授权的 ``DROP`` 被真正跑出来。
2. **``"retry"``** —— 执行报错且仍在重试预算内（``error`` 且 ``retries < MAX_RETRIES``）。
3. **``"end"``** —— 其余情形（成功，或重试次数用尽）。

``build_graph`` 用 ``functools.partial`` 把 ``llm`` / ``db_url`` 绑定进各节点，
让它们退化成「只接受 ``state`` 一个参数」的真正 LangGraph 节点；再按拓扑连边、
挂条件路由、编译返回。
"""

from __future__ import annotations

import functools

from langgraph.graph import END, START, StateGraph

from .guardrail import is_destructive
from .nodes import execute_sql, generate_sql, reflect_and_rewrite
from .state import AgentState

# 自愈循环的最大重试次数：超过即放弃，路由到 "end"。
MAX_RETRIES = 3


def should_retry(state: AgentState) -> str:
    """``execute_sql`` 之后的条件路由函数。

    返回三态之一：

    - ``"human"``：高危 SQL 且未审批 → 等人工介入（``END``）。
    - ``"retry"``：有报错且 ``retries < MAX_RETRIES`` → 进反思重写。
    - ``"end"``：成功，或重试预算耗尽。
    """
    if is_destructive(state["sql"]) and not state["approved"]:
        return "human"
    if state["error"] and state["retries"] < MAX_RETRIES:
        return "retry"
    return "end"


def build_graph(llm, db_url: str, checkpointer=None):
    """构建并编译自愈状态机。

    用 ``functools.partial`` 把 ``llm`` / ``db_url`` 绑到节点上，使其只剩
    ``state`` 一个入参（LangGraph 节点契约）；再按拓扑连边、加条件路由，
    最后以可选 ``checkpointer`` 编译返回 ``CompiledGraph``。
    """
    graph = StateGraph(AgentState)

    graph.add_node("generate_sql", functools.partial(generate_sql, llm=llm, db_url=db_url))
    graph.add_node("execute_sql", functools.partial(execute_sql, db_url=db_url))
    graph.add_node("reflect_and_rewrite", functools.partial(reflect_and_rewrite, llm=llm))

    graph.add_edge(START, "generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_conditional_edges(
        "execute_sql",
        should_retry,
        {"retry": "reflect_and_rewrite", "human": END, "end": END},
    )
    graph.add_edge("reflect_and_rewrite", "execute_sql")

    return graph.compile(checkpointer=checkpointer)


__all__ = ["MAX_RETRIES", "should_retry", "build_graph"]
