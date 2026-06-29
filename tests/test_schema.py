from sqlalchemy import create_engine, text
from sql_self_healer.schema import load_schema, get_sample_data


def _setup(db_url):
    eng = create_engine(db_url)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'alice'), (2, 'bob')"))
        conn.commit()
    return eng


def test_load_schema_contains_table_and_columns(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    _setup(db_url)
    schema_str = load_schema(db_url)
    assert "users" in schema_str
    assert "name" in schema_str


def test_get_sample_data_returns_rows(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    _setup(db_url)
    rows = get_sample_data(db_url, "users", n=3)
    assert len(rows) == 2
    assert rows[0]["name"] in ("alice", "bob")


def test_load_schema_marks_primary_key(tmp_path):
    # 回归测试：确保 [PK] 标记出现且 PK 列强制显示为 NOT NULL。
    # 旧代码用错误的字典 key（pk_columns）导致标记永久丢失。
    db_url = f"sqlite:///{tmp_path}/test.db"
    _setup(db_url)
    schema_str = load_schema(db_url)
    assert "[PK]" in schema_str
    assert "id: INTEGER NOT NULL [PK]" in schema_str
