"""Dynamic DB schema introspection.

Connects to a database via SQLAlchemy 2.0, enumerates tables and columns,
and returns the schema as a context string suitable for prompting an LLM
to generate SQL. SQLite by default (any SQLAlchemy-supported URL works).
"""

from __future__ import annotations

import sqlalchemy
from sqlalchemy import create_engine, inspect, text


def get_sample_data(db_url: str, table: str, n: int = 3) -> list[dict]:
    """Return up to ``n`` sample rows from ``table`` as a list of dicts.

    Uses SQLAlchemy 2.0 style execution: ``text()`` + ``.mappings().all()``.
    """
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table} LIMIT {n}"))
            rows = [dict(row) for row in result.mappings().all()]
        return rows
    finally:
        engine.dispose()


def load_schema(db_url: str) -> str:
    """Introspect the database and return a schema description string.

    Enumerates each table's columns (name, type, nullable, primary key)
    and appends a few sample rows per table so the LLM can ground its
    SQL generation in the actual structure and data.
    """
    engine = create_engine(db_url)
    try:
        insp = inspect(engine)
        table_names = insp.get_table_names()

        parts: list[str] = []
        if not table_names:
            return "Database has no tables."

        parts.append(f"Database tables ({len(table_names)}):")
        for table in table_names:
            parts.append(f"\n## Table: {table}")
            columns = insp.get_columns(table)
            # SQLAlchemy 2.0 中 get_pk_constraint 返回字典的标准 key 是
            # constrained_columns（实测 {'constrained_columns': ['id'], ...}）。
            # 旧代码误用 pk_columns 导致 .get 永远返回 None，[PK] 标记丢失。
            pk_cols = set(insp.get_pk_constraint(table).get("constrained_columns", []) or [])

            parts.append("Columns:")
            for col in columns:
                pk_marker = " [PK]" if col["name"] in pk_cols else ""
                # SQLite 反射 INTEGER PRIMARY KEY 时 nullable=True（方言怪癖），
                # 对读者反直觉；主键在语义上必须 NOT NULL，这里强制纠正显示。
                is_pk = col["name"] in pk_cols or col.get("primary_key")
                nullable = "NOT NULL" if is_pk else ("NULL" if col.get("nullable", True) else "NOT NULL")
                col_type = str(col.get("type", "UNKNOWN"))
                parts.append(
                    f"  - {col['name']}: {col_type} {nullable}{pk_marker}"
                )

            # Sample rows to help the LLM ground its SQL.
            sample = get_sample_data(db_url, table, n=3)
            if sample:
                parts.append(f"Sample rows ({len(sample)}):")
                for row in sample:
                    parts.append(f"  {row}")
            else:
                parts.append("Sample rows: (empty table)")

        return "\n".join(parts)
    finally:
        engine.dispose()


__all__ = ["load_schema", "get_sample_data"]
