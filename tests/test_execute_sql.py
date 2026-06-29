"""``execute_sql`` 的回归测试：聚焦「不返回行」语句的 returns_rows 守卫。

背景：SQLAlchemy 2.0 对 DDL（DROP/CREATE/ALTER）与无返回行的 DML
（TRUNCATE、无 WHERE 的 DELETE/UPDATE）的结果对象，调 ``mappings()``
会抛 "This result object does not return rows"。早期实现无条件走
``mappings().all()``，导致这些语句被 except 捕成伪 error，进而误触
``should_retry`` 的 retry 分支重试三轮。这里直接断言修复后的契约：
- 不返回行的语句 → ``error == ""``，且副作用（建表/删表/清表）确实落库；
- 返回行的语句（SELECT）→ 原有 TSV 行为不被破坏。

测试自建临时 sqlite 库，不依赖 LangGraph，可独立 ``pytest`` 跑通。
"""

from sqlalchemy import create_engine, inspect, text

from sql_self_healer.nodes import execute_sql


def _db_with_users(tmp_path) -> str:
    """建一个带 users 表（含两行）的临时 sqlite 库，返回 db_url。"""
    db = f"sqlite:///{tmp_path}/t.db"
    eng = create_engine(db)
    with eng.connect() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        c.execute(text("INSERT INTO users (id, name) VALUES (1, 'alice'), (2, 'bob')"))
        c.commit()
    eng.dispose()
    return db


def _table_exists(db: str, table: str) -> bool:
    """用 inspect 反射判断表是否还在（避免再写 SQL 触发 execute_sql）。"""
    return table in inspect(create_engine(db)).get_table_names()


def test_drop_approved_no_pseudo_error_and_table_gone(tmp_path):
    """DROP（已审批）走 execute_sql：无伪错，且表确实被删。"""
    db = _db_with_users(tmp_path)
    assert _table_exists(db, "users")  # 前置：表确实在

    out = execute_sql({"sql": "DROP TABLE users", "approved": True}, db)

    # 核心断言：不返回行的 DDL 不再被当成错误。
    assert out["error"] == ""
    assert out["result"] == "(no rows)"
    # 副作用断言：DROP 真正落库（commit 生效），users 表已不存在。
    assert not _table_exists(db, "users")


def test_delete_without_where_approved_clears_rows(tmp_path):
    """无 WHERE 的 DELETE（已审批）也不返回行：无伪错，且行被清空。"""
    db = _db_with_users(tmp_path)

    out = execute_sql({"sql": "DELETE FROM users", "approved": True}, db)

    assert out["error"] == ""
    assert out["result"] == "(no rows)"
    # 表还在，但行已清空——用一条独立 SELECT 复核。
    eng = create_engine(db)
    with eng.connect() as c:
        rows = c.execute(text("SELECT COUNT(*) FROM users")).scalar()
    eng.dispose()
    assert rows == 0


def test_create_table_approved_no_pseudo_error(tmp_path):
    """CREATE TABLE（已审批）同样不返回行：无伪错，且新表落库。"""
    db = f"sqlite:///{tmp_path}/empty.db"
    eng = create_engine(db)
    eng.dispose()

    out = execute_sql(
        {"sql": "CREATE TABLE logs (id INTEGER PRIMARY KEY, msg TEXT)", "approved": True},
        db,
    )

    assert out["error"] == ""
    assert out["result"] == "(no rows)"
    assert _table_exists(db, "logs")


def test_select_path_still_returns_tsv(tmp_path):
    """SELECT 路径（returns_rows=True）保持原有 TSV 格式，未被守卫改坏。"""
    db = _db_with_users(tmp_path)

    out = execute_sql({"sql": "SELECT id, name FROM users ORDER BY id", "approved": True}, db)

    assert out["error"] == ""
    # 首行表头 + 两行数据，制表符分隔。
    expected = "id\tname\n1\talice\n2\tbob"
    assert out["result"] == expected


def test_select_empty_result_returns_no_rows(tmp_path):
    """返回行但结果为空：仍走 (no rows) 成功态（原有语义保持一致）。"""
    db = _db_with_users(tmp_path)

    out = execute_sql({"sql": "SELECT * FROM users WHERE id = 999", "approved": True}, db)

    assert out["error"] == ""
    assert out["result"] == "(no rows)"
