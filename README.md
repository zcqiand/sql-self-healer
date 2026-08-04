# sql-self-healer

自然语言转 SQL + 报错自愈（LangGraph）。配套《Codex 从入门到项目实践》卷四。

## 快速开始

```bash
pip install -e ".[dev]"    # 安装依赖
pytest -q                   # 跑全部测试（FakeLLM，无需 API Key）
```

## 功能特性

- **动态 Schema 注入**：运行时 schema 感知，无静态表结构依赖
- **自愈状态机**：SQL 执行失败后自动重试与修正
- **HITL 安全熔断**：人工介入（Human-in-the-Loop）安全机制
- **异步并发接口**：FastAPI 异步 API 层

## 技术栈

| 技术 | 版本 |
| :--- | :--- |
| Python | 3.11+ |
| LangGraph | 1.2.x |
| SQLAlchemy | 2.0 |
| SQLite（默认） | — |
| 测试框架 | pytest 8.x |

> 依赖版本与 `version-lock.json` 的 `version_lock` 一致，不引入 lock 外的库。

## 配套书籍及章节映射

| 章 | 主题 | 对应源文件 |
| :--- | :--- | :--- |
| 22 | 动态 Schema 注入 | `schema.py` |
| 23 | 自愈状态机 | `graph.py`, `nodes.py`, `state.py` |
| 24 | HITL 安全熔断 | `guardrail.py`, `graph.py`（`should_retry`） |
| 25 | 异步并发接口 | `api.py` |

## 快速链接

- [功能规格文档.md](功能规格文档.md) — 功能名称、描述与验收标准
- [CLAUDE.md](CLAUDE.md) — 开发约定与编码规范
