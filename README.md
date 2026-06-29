# sql-self-healer

自然语言转 SQL + 报错自愈（LangGraph）。

本书 xr-know-008 卷四案例仓之一。仓库随章节迭代：本任务只含仓骨架、
`AgentState` 全局状态、以及离线 `FakeLLM`，后续任务逐步补齐 schema /
graph / guardrail / api 模块。

## 章节映射表

| 章节 | 本仓库对应 |
| ---- | ---------- |
| 22 动态 Schema 注入 | `schema.py` |
| 23 自愈状态机 | `graph.py`、`nodes.py`、`state.py` |
| 24 HITL 安全熔断 | `guardrail.py`、`graph.py`（`should_retry`） |
| 25 异步并发接口 | `api.py` |
