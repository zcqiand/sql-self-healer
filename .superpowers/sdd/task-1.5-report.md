# Task 1.5 — LangGraph 自愈状态机

## 概述
把已有的 `generate_sql` / `execute_sql` / `reflect_and_rewrite` 三节点连成
LangGraph 1.2.x 的 `StateGraph` 自愈状态机，加入三态条件路由 `should_retry`
和「未授权高危 SQL 跳过执行」的安全围栏。

## 变更文件
- **新增** `src/sql_self_healer/graph.py`
  - `MAX_RETRIES = 3` 模块常量。
  - `should_retry(state) -> str`：三态优先级 `human` > `retry` > `end`。
  - `build_graph(llm, db_url, checkpointer=None)`：`StateGraph(AgentState)`，
    `functools.partial` 绑定 `llm`/`db_url`，按拓扑连边 +
    `add_conditional_edges("execute_sql", should_retry, {retry/human/end})`，
    `graph.compile(checkpointer=checkpointer)` 返回编译图。
- **修改** `src/sql_self_healer/nodes.py`
  - `execute_sql` 顶部加安全围栏：当
    `is_destructive(state["sql"]) and not state.get("approved", False)` 时
    直接返回 `{"result": "", "error": ""}` 跳过执行，让 `should_retry`
    路由到 `"human"`；保证未授权 DROP 永不落地。用 `.get("approved", False)`
    而非下标取键，避免缺键 KeyError。
  - 新增 `from .guardrail import is_destructive` 导入。
- **新增** `tests/test_graph.py`（按规格逐字）。

## 安装
`pip install langgraph` → 装入 `langgraph-1.2.6`（+ 依赖 langchain-core 1.4.8、
langgraph-checkpoint 4.1.1、langgraph-prebuilt 1.1.0、langgraph-sdk 0.4.2、
langsmith 0.9.3、tenacity 9.1.4、uuid-utils、xxhash、zstandard、websockets 15 等）。
有一个**已存在**的无关依赖冲突：`gradio 3.41.2 / gradio-client 0.5.0` 要求
`websockets<12`，本次升级到 15。不影响 sql-self-healer（它不依赖 gradio）。

## FAIL（实现前）
```
$ pytest tests/test_graph.py -q
ERROR collecting tests/test_graph.py
E   ModuleNotFoundError: No module named 'sql_self_healer.graph'
1 error in 0.35s
```

## PASS（实现后）
```
$ pytest tests/test_graph.py -q
..                                                                       [100%]
2 passed in 0.45s
```

## 全量测试
```
$ pytest -q
...................                                                      [100%]
19 passed in 0.54s
```
19 个测试全绿（1.1 state / 1.2 schema / 1.3 guardrail / 1.4 nodes / 1.5 graph）。

## 提交
- 分支：`feat/guardrail-and-nodes`（仓库当前分支，未推送）
- hash：`8be8914c6173637cf8f9a1cc17eb07b74f3f55e6`
- message：`feat(sql-healer): LangGraph 自愈状态机 (build_graph/should_retry)`
- 3 files changed, 125 insertions(+)

## 关键设计点
- **围栏位置**：规格要求「若 `nodes.execute_sql` 没有此守卫则补上」。原实现没有，
  遂在 `execute_sql` 顶部加守卫。守卫只命中高危+未审批语句；现有 nodes 测试用的
  都是 SELECT（非高危），`approved` 取值不影响它们，`test_nodes.py` 保持绿。
- **路由优先级**：`human` 判断在前，确保即便带 error 的高危未审批语句也走人工审批
  而非自愈重试——自愈只对非高危的报错 SQL（语法错等）有意义。
- **`should_retry` 的 ``error`` 判断**：`execute_sql` 在围栏命中时返回空 error，
  因此「高危未审批」一定走 `human` 分支，不会误入 `retry`。

## 关注点 / LangGraph 1.2 API 备注
1. **无 API 惊喜**。1.2.x 的 `from langgraph.graph import StateGraph, START, END`
   入口、`add_node` / `add_edge` / `add_conditional_edges` / `compile(checkpointer=)`
   全部按规格所述工作。`START`/`END` 确实是常量（实测值 `__start__` / `__end__`）。
2. **`add_conditional_edges` 的字典映射**显式给出三条出口，比让 LangGraph 用
   函数返回值当隐式节点名更稳健（也是规格写法）。
3. **TypedDict 作为 StateGraph schema**：直接传 `StateGraph(AgentState)` 即可，
   无需自定义 reducer——所有字段都是覆盖语义（节点返回部分字典，LangGraph 原地覆盖），
   对本场景（每步只更新 sql/error/retries/result 中的若干个）正确。
4. **`functools.partial` 绑定 keyword 参数**与节点函数签名
   (`def generate_sql(state, llm, db_url)`) 配合无歧义，编译后的节点只剩 `state`
   一个位置入参，符合 LangGraph 节点契约。
5. **Python 3.10 兼容**：仓库 `pyproject.toml` 写 `requires-python = ">=3.11"`
   且 CLAUDE.md 标 3.11+，但本地实际是 3.10.6。代码只用 `from __future__ import annotations`
   + 标准 typing，无 3.11-only 语法；LangGraph 1.2.6 在 3.10 上正常导入运行。
   pyproject 的 `>=3.11` 与实际 3.10.6 不一致，但不阻塞——可留待后续清理。
6. **未建 `api.py`**（Task 1.6 范围，严格遵守 scope）。
