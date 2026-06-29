"""LangGraph 全局状态定义。

``AgentState`` 在各节点间传递：自然语言查询、生成的 SQL、执行报错、
重试次数、查询结果、租户隔离标识、人工审批标志。
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    """Agent 各节点共享的全局状态。"""

    query: str
    sql: str
    error: str
    retries: int
    result: str
    tenant_id: str
    approved: bool
