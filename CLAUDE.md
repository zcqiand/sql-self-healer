# sql-self-healer — 仓库工作约定（供 Claude Code）

本仓为《Codex 从入门到项目实践》卷四案例仓（自然语言转 SQL 自愈）的可运行配套工程，是书稿代码块的 **source of truth**。

## 项目定位

自然语言转 SQL + 报错自愈的 LangGraph Agent，用于演示动态 schema 注入、自愈状态机、HITL 安全熔断与异步并发接口。

## 铁律

- **TDD**：每个模块先写失败测试 → 跑确认失败 → 实现 → 跑确认绿 → commit。
- **版本钉死**：依赖与 `version-lock.json` 的 `version_lock` 一致；不引入 lock 外的库。
- **tag 即放行**：全量回归绿后打 `v<MAJOR>.<MINOR>-<NNN>`（NNN=项目号）。
- **只增不改**：扩充时不动现有模块签名/行为；新模块独立测试，CI 双跑。
- **mock-friendly**：`pip install -e ".[dev]" && pytest -q` 必须在无 Key、无 Docker、无网下全绿。

## 技术栈与版本（钉死于 version-lock.json）

- Python 3.11+
- LangGraph 1.2.x
- SQLAlchemy 2.0
- SQLite（默认）
- pytest 8.x

## 验收

```bash
pip install -e ".[dev]"    # 离线可用（首次需联网，之后 node_modules 已就绪）
pytest -q                   # 必须全绿，无需 Key/Docker/网络
```

## 目录结构

```text
sql-self-healer/
├── pyproject.toml
├── CLAUDE.md
├── version-lock.json
├── src/
│   ├── schema.py                  ← Ch22 动态 Schema 注入
│   ├── state.py
│   ├── graph.py                   ← Ch23 自愈状态机
│   ├── nodes.py
│   ├── guardrail.py               ← Ch24 HITL 安全熔断
│   └── api.py                     ← Ch25 异步并发接口
└── tests/
```

## 编码约定

- **FakeLLM 驱动**：所有测试用 `FakeLLM`，无需任何 API Key、无需联网。
- **零伪代码**：禁止 `pass` 占位、`TODO` 占位，每段代码必须可运行。
- **危险 SQL 拦截**：DDL / TRUNCATE / DROP 等高危操作必须被 guardrail 正确拦截。
