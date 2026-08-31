"""FastAPI 异步并发接口：把 LangGraph 自愈状态机暴露为 ``POST /query``。

请求体（``QueryRequest``）：自然语言 ``query``、多租户 ``tenant_id``、
目标库 ``DATABASE_URL``。响应体（``QueryResponse``）：最终 SQL、执行结果、报错。

设计要点
~~~~~~~~

- ``get_llm`` 是一个可被 ``app.dependency_overrides`` 替换的依赖工厂，
  测试时覆写为 ``FakeLLM``，从而在无 API Key 下驱动整条状态机。
- 端点内即时 ``build_graph`` 把 ``llm`` / ``DATABASE_URL`` 绑进节点，
  ``graph.invoke`` 驱动「生成 → 执行 → 反思重写」自愈循环。
  （节点是 ``functools.partial`` 包出来的同步函数，因此走同步 ``invoke``；
  如需真正异步并发，可把节点改写为 ``async def`` 再用 ``ainvoke``。）
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from .graph import build_graph
from .llm import make_llm

app = FastAPI(title="SQL Self-Healer")


class QueryRequest(BaseModel):
    """``/query`` 请求体。"""

    query: str
    tenant_id: str = "default"
    DATABASE_URL: str = "sqlite:///./data/sample.db"


class QueryResponse(BaseModel):
    """``/query`` 响应体。"""

    sql: str
    result: str
    error: str


def get_llm():
    """LLM 依赖工厂：默认走 ``make_llm``（无 Key 时返回 FakeLLM）。"""
    return make_llm()


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, llm=Depends(get_llm)) -> QueryResponse:
    """把自然语言查询跑过自愈状态机，返回最终 SQL / 结果 / 报错。"""
    graph = build_graph(llm=llm, DATABASE_URL=req.DATABASE_URL)
    initial = {
        "query": req.query,
        "sql": "",
        "error": "",
        "retries": 0,
        "result": "",
        "tenant_id": req.tenant_id,
        "approved": True,
    }
    out = graph.invoke(initial)
    return QueryResponse(
        sql=out.get("sql", ""),
        result=out.get("result", ""),
        error=out.get("error", ""),
    )


__all__ = ["app", "QueryRequest", "QueryResponse", "get_llm", "query"]
