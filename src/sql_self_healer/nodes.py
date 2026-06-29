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
    """
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(state["sql"]))
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
