from sql_self_healer.guardrail import is_destructive, classify


def test_drop_is_destructive():
    assert is_destructive("DROP TABLE users") is True

def test_truncate_is_destructive():
    assert is_destructive("TRUNCATE TABLE logs") is True

def test_select_is_safe():
    assert is_destructive("SELECT * FROM users") is False

def test_delete_without_where_is_destructive():
    assert is_destructive("DELETE FROM users") is True

def test_delete_with_where_is_write_not_destructive():
    assert is_destructive("DELETE FROM users WHERE id = 1") is False

def test_classify_read():
    assert classify("SELECT 1") == "read"

def test_classify_write():
    assert classify("INSERT INTO users VALUES (1)") == "write"

def test_classify_destructive():
    assert classify("DROP TABLE users") == "destructive"
