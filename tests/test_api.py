"""FastAPI ``/query`` 端点测试。

用 ``FastAPI.TestClient`` + ``FakeLLM`` 驱动：先在临时 SQLite 库里建表
插数据，再把 ``get_llm`` 依赖覆写成返回固定 SQL 的 ``FakeLLM``，
最后 POST ``/query`` 验证 ``sql`` 非空、状态码 200。
无需任何 API Key 或网络。
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from sql_self_healer.api import app, get_llm
from sql_self_healer.llm import FakeLLM


def test_query_endpoint(tmp_path):
    db = f"sqlite:///{tmp_path}/t.db"
    eng = create_engine(db)
    with eng.connect() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        c.execute(text("INSERT INTO users (id, name) VALUES (1, 'alice')"))
        c.commit()
    eng.dispose()

    app.dependency_overrides[get_llm] = lambda: FakeLLM(script=["SELECT * FROM users"])
    try:
        client = TestClient(app)
        resp = client.post(
            "/query",
            json={"query": "列出用户", "tenant_id": "t1", "DATABASE_URL": db},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sql"]  # non-empty
        assert "alice" in body["result"]
        assert body["error"] == ""
    finally:
        app.dependency_overrides.clear()
