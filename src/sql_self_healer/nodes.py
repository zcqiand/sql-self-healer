"""LangGraph 节点函数：generate_sql / execute_sql / reflect_and_rewrite。

每个节点都是纯函数：读取所需状态字段，返回一个**部分状态字典**，
LangGraph 在合并时会把这些字段写回全局 ``AgentState``。

为了能脱离图独立测试，节点显式接收 ``llm`` 与 ``db_url`` 参数；
后续 ``graph.py``（更后的任务）会用 ``functools.partial`` 把它们
绑定成「只接受 ``state`` 一个参数」的真正 LangGraph 节点。

SQLAlchemy 一律走 2.0 风格：``text()`` 包裹 SQL，``connection.execute``
执行，``.mappings().all()`` 取行。引擎在 finally 中 ``dispose``，
避免连接泄漏。
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .guardrail import is_destructive
from .schema import load_schema
from .state import AgentState


def generate_sql(state: AgentState, llm, db_url: str) -> dict:
    """调用 LLM 把自然语言查询翻译成 SQL。

    提示词注入 ``load_schema(db_url)`` 反射出的表结构与样例数据，
    以及用户的自然语言 ``state["query"]``，再交给 ``llm.generate``
    产出可执行 SQL。

    返回部分状态 ``{"sql": <LLM 输出>}``。
    """
    schema = load_schema(db_url)
    prompt = (
        "You are a SQL expert. Given the database schema below and a "
        "natural-language question, output ONLY the single SQL statement "
        "that answers the question — no markdown, no explanation.\n\n"
        f"### SCHEMA\n{schema}\n\n"
        f"### QUESTION\n{state['query']}\n\n"
        "### SQL\n"
    )
    sql = llm.generate(prompt)
    return {"sql": sql}


def execute_sql(state: AgentState, db_url: str) -> dict:
    """执行 ``state["sql"]``，返回结果行或报错信息。

    成功：``{"result": <格式化后的行字符串>, "error": ""}``。
    抛 ``SQLAlchemyError``：``{"result": "", "error": <str(exc)>}``。
    引擎无论成败都会 ``dispose``。

    安全围栏：当 ``is_destructive(state["sql"]) and not state["approved"]``
    时**跳过执行**——返回 ``{"result": "", "error": ""}``，让路由节点
    ``should_retry`` 把流程引向 ``"human"``（人工审批），从而保证一条未授权的
    ``DROP`` 永远不会真正落到数据库上。

    ``returns_rows`` 守卫：DDL（DROP/CREATE/ALTER）与无返回行的 DML
    （TRUNCATE、无 WHERE 的 DELETE/UPDATE）在 SQLAlchemy 2.0 下
    ``result.mappings()`` 会抛「does not return rows」，故先用
    ``result.returns_rows`` 把这类语句分流到「提交事务、返回 (no rows) 成功态」
    分支，避免被 except 当成伪错误、误触重试循环。
    """
    if is_destructive(state["sql"]) and not state.get("approved", False):
        return {"result": "", "error": ""}

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(state["sql"]))
            if not result.returns_rows:
                # DDL/无返回行 DML：SQLAlchemy 2.0 下 mappings() 会抛异常，
                # 这里显式 commit 让改动落库（SQLite 对 DDL 与无 WHERE 的
                # DELETE 同样需要显式提交），并以 (no rows) 成功态返回。
                conn.commit()
                return {"result": "(no rows)", "error": ""}
            rows = result.mappings().all()

        if not rows:
            return {"result": "(no rows)", "error": ""}

        # 列名来自第一行的映射键，顺序与首行一致。
        columns = list(rows[0].keys())
        lines = ["\t".join(str(c) for c in columns)]
        for row in rows:
            lines.append("\t".join(str(row[c]) for c in columns))
        return {"result": "\n".join(lines), "error": ""}
    except SQLAlchemyError as exc:
        return {"result": "", "error": str(exc)}
    finally:
        engine.dispose()


def reflect_and_rewrite(state: AgentState, llm) -> dict:
    """把执行报错反馈给 LLM，生成修正后的 SQL。

    提示词包含失败的 SQL 与报错信息，要求 LLM 输出修复版本。
    返回 ``{"sql": <新 SQL>, "retries": state["retries"] + 1}``。
    """
    prompt = (
        "The following SQL failed with the given error. Output ONLY the "
        "corrected SQL — no markdown, no explanation.\n\n"
        f"### FAILED SQL\n{state['sql']}\n\n"
        f"### ERROR\n{state['error']}\n\n"
        "### CORRECTED SQL\n"
    )
    sql = llm.generate(prompt)
    return {"sql": sql, "retries": state["retries"] + 1}


__all__ = ["generate_sql", "execute_sql", "reflect_and_rewrite"]
