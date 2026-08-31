from sqlalchemy import create_engine, text
from sql_self_healer.state import AgentState
from sql_self_healer.llm import FakeLLM
from sql_self_healer.nodes import generate_sql, execute_sql, reflect_and_rewrite


def _state(**over):
    base = {"query": "", "sql": "", "error": "", "retries": 0, "result": "", "tenant_id": "t1", "approved": False}
    base.update(over)
    return base


def _db(tmp_path):
    db = f"sqlite:///{tmp_path}/t.db"
    eng = create_engine(db)
    with eng.connect() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        c.commit()
    return db


def test_generate_sql_uses_llm(tmp_path):
    db = _db(tmp_path)
    llm = FakeLLM(script=["SELECT * FROM users LIMIT 1"])
    out = generate_sql(_state(query="列出用户"), llm=llm, DATABASE_URL=db)
    assert out["sql"] == "SELECT * FROM users LIMIT 1"


def test_execute_sql_captures_error(tmp_path):
    db = _db(tmp_path)
    out = execute_sql(_state(sql="SELECT FROM broken_table"), DATABASE_URL=db)
    assert out["error"] != ""
    assert out["result"] == ""


def test_execute_sql_returns_result(tmp_path):
    db = _db(tmp_path)
    out = execute_sql(_state(sql="SELECT 1 AS one"), DATABASE_URL=db)
    assert out["error"] == ""
    assert "one" in (out["result"] or "")


def test_reflect_increments_retries_and_rewrites():
    llm = FakeLLM(script=["SELECT 2"])
    out = reflect_and_rewrite(_state(error="near FROM: syntax error", retries=1), llm=llm)
    assert out["retries"] == 2
    assert out["sql"] == "SELECT 2"
