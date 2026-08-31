from sqlalchemy import create_engine, text, inspect
from sql_self_healer.graph import build_graph
from sql_self_healer.llm import FakeLLM


def _db(tmp_path, with_users=True):
    db = f"sqlite:///{tmp_path}/t.db"
    eng = create_engine(db)
    if with_users:
        with eng.connect() as c:
            c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
            c.commit()
    return db


def _initial(query="列出用户", approved=True):
    return {"query": query, "sql": "", "error": "", "retries": 0, "result": "", "tenant_id": "t1", "approved": approved}


def test_self_heal_loop(tmp_path):
    db = _db(tmp_path)
    llm = FakeLLM(script=["SELECT FROM broken", "SELECT * FROM users"])  # bad → good
    g = build_graph(llm=llm, DATABASE_URL=db)
    out = g.invoke(_initial())
    assert out["error"] == ""
    assert out["result"] != ""   # healed and executed successfully


def test_destructive_routes_to_human_not_executed(tmp_path):
    db = _db(tmp_path)
    llm = FakeLLM(script=["DROP TABLE users"])
    g = build_graph(llm=llm, DATABASE_URL=db)
    out = g.invoke(_initial(query="删表", approved=False))
    # destructive + not approved → human (END), table must still exist (not dropped)
    assert inspect(create_engine(db)).get_table_names()  # users still there
    assert "users" in inspect(create_engine(db)).get_table_names()
