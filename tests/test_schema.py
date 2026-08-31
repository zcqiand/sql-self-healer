from sqlalchemy import create_engine, text
from sql_self_healer.schema import load_schema, get_sample_data


def _setup(DATABASE_URL):
    eng = create_engine(DATABASE_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'alice'), (2, 'bob')"))
        conn.commit()
    return eng


def test_load_schema_contains_table_and_columns(tmp_path):
    DATABASE_URL = f"sqlite:///{tmp_path}/test.db"
    _setup(DATABASE_URL)
    schema_str = load_schema(DATABASE_URL)
    assert "users" in schema_str
    assert "name" in schema_str


def test_get_sample_data_returns_rows(tmp_path):
    DATABASE_URL = f"sqlite:///{tmp_path}/test.db"
    _setup(DATABASE_URL)
    rows = get_sample_data(DATABASE_URL, "users", n=3)
    assert len(rows) == 2
    assert rows[0]["name"] in ("alice", "bob")


def test_load_schema_marks_primary_key(tmp_path):
    # 回归测试：确保 [PK] 标记出现且 PK 列强制显示为 NOT NULL。
    # 旧代码用错误的字典 key（pk_columns）导致标记永久丢失。
    DATABASE_URL = f"sqlite:///{tmp_path}/test.db"
    _setup(DATABASE_URL)
    schema_str = load_schema(DATABASE_URL)
    assert "[PK]" in schema_str
    assert "id: INTEGER NOT NULL [PK]" in schema_str
