"""高危 SQL 拦截与语句分类。

``is_destructive`` 判定一条 SQL 是否会对数据造成不可逆破坏：

- ``DROP`` / ``TRUNCATE`` —— 永远视为高危（丢表/清表）。
- ``DELETE`` / ``UPDATE`` —— 仅当**不带 WHERE 子句**时视为高危
  （无 WHERE 的全表删除/更新极其危险）。
- 其余（``SELECT`` / ``INSERT``，或带 WHERE 的 DELETE/UPDATE）安全。

``classify`` 在 ``is_destructive`` 基础上进一步把语句归入
``destructive`` / ``write`` / ``read`` 三类，供路由节点决策。

实现说明：优先用 ``sqlparse`` 解析出语句首个 DML/DDL 关键字；
WHERE 子句检测则退回正则（sqlparse 的 token 流对 WHERE 的提取
在不同写法下不稳定，正则对「整条语句是否出现 WHERE 关键字」更可靠）。
"""

from __future__ import annotations

import re

import sqlparse

# 永远高危的语句首关键字（大小写无关）。
_ALWAYS_DESTRUCTIVE = {"DROP", "TRUNCATE"}
# 受 WHERE 保护的有害写操作关键字。
_CONDITIONAL_WRITE = {"DELETE", "UPDATE"}
# 所有写操作关键字（用于 classify 的 write 归类）。
_WRITE_STMTS = {"INSERT", "UPDATE", "DELETE"}

# 匹配独立的 WHERE 关键字（词边界，避免命中列名/别名）。
_WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)
# 兜底：直接匹配语句首个关键字（sqlparse 不可用或解析异常时）。
_FIRST_KEYWORD_RE = re.compile(r"^\s*([A-Za-z]+)")


def _first_keyword(sql: str) -> str:
    """返回 SQL 首个关键字（大写）；无法解析时返回空串。"""
    sql = (sql or "").strip()
    if not sql:
        return ""

    # 优先用 sqlparse 抓取语句类型关键字。
    try:
        parsed = sqlparse.parse(sql)
        if parsed:
            for tok in parsed[0].tokens:
                # Keyword / DML / DDL token 的 ttype 末端名为 Keyword。
                if tok.is_keyword or (
                    tok.ttype is not None and "Keyword" in str(tok.ttype)
                ):
                    kw = tok.value.strip().upper()
                    if kw:
                        return kw
    except Exception:  # noqa: BLE001 - 解析失败时退回正则
        pass

    match = _FIRST_KEYWORD_RE.match(sql)
    return match.group(1).upper() if match else ""


def is_destructive(sql: str) -> bool:
    """判断 SQL 是否高危。

    - ``DROP``/``TRUNCATE`` —— 永远 True。
    - ``DELETE``/``UPDATE`` —— 无 WHERE 子句时 True，有 WHERE 时 False。
    - 其余（``SELECT``/``INSERT`` 等）—— False。
    """
    kw = _first_keyword(sql)
    if kw in _ALWAYS_DESTRUCTIVE:
        return True
    if kw in _CONDITIONAL_WRITE:
        # DELETE/UPDATE 是否带 WHERE：用正则检测整条语句。
        return _WHERE_RE.search(sql or "") is None
    return False


def classify(sql: str) -> str:
    """把 SQL 归类为 ``destructive`` / ``write`` / ``read``。

    - 高危语句（见 ``is_destructive``）→ ``"destructive"``。
    - 其余 INSERT/UPDATE/DELETE → ``"write"``。
    - SELECT（及任何非写操作）→ ``"read"``。
    """
    if is_destructive(sql):
        return "destructive"
    kw = _first_keyword(sql)
    if kw in _WRITE_STMTS:
        return "write"
    return "read"


__all__ = ["is_destructive", "classify"]
