# sql-self-healer — 项目级上下文

自然语言转 SQL + 报错自愈的 LangGraph Agent（本书 xr-know-008 卷四案例仓之一）。

- 技术栈：Python 3.11+ / LangGraph 1.2.x / SQLAlchemy 2.0 / SQLite（默认）
- 测试用 `FakeLLM`，无需任何 API Key、无需联网
- 运行：`pytest -q`（无 API Key）
