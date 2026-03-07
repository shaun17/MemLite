# MemLite 调用链路与问题审计（源码视角）

日期：2026-03-07
范围：`src/memlite/*` + 关键集成测试

## 1) 启动链路（REST）

1. `memlite-server` -> `memlite.app.main:main()` 启动 Uvicorn。
2. `create_app()` 注入 `ResourceManager.create(settings)`，挂到 `app.state.resources`。
3. FastAPI `lifespan` 调 `resources.initialize()`：
   - 初始化 SQLite schema
   - 初始化 semantic/derivative 向量表
   - 初始化 Kùzu schema
   - 跑 startup recovery（reconcile + backlog gauge）
4. API 路由通过 `api/deps.py#get_resources()` 取资源，调用 orchestrator 或 store/service。

涉及文件：
- `src/memlite/app/main.py`
- `src/memlite/app/resources.py`
- `src/memlite/app/background.py`
- `src/memlite/api/deps.py`

## 2) 写入链路（POST /memories）

1. `api/memories.py:add_memories()` 调 `orchestrator.add_episodes(...)`。
2. `orchestrator.add_episodes()`：
   - 先写 SQLite `episodes`（source of truth）
   - 再对每条 episode 调 `DerivativePipeline.create_derivatives()`
   - 若传 `semantic_set_id`，把 history_id 加入 `semantic_set_ingested_history`
   - 写短期记忆窗口（`ShortTermMemory`）
3. `DerivativePipeline.create_derivatives()`：
   - 句级切分 content
   - 在 Kùzu 写 Episode/Derivative 节点和 `DERIVED_FROM` 边
   - 用 embedder 生成向量，写入 `derivative_feature_vectors`

涉及文件：
- `src/memlite/api/memories.py`
- `src/memlite/orchestrator/memory_orchestrator.py`
- `src/memlite/storage/episode_store.py`
- `src/memlite/episodic/derivative_pipeline.py`
- `src/memlite/storage/graph_store.py`
- `src/memlite/storage/sqlite_vec.py`
- `src/memlite/memory/short_term_memory.py`

## 3) 检索链路（POST /memories/search）

1. API 层把 query/session/filter 参数传给 `orchestrator.search_memories()`。
2. orchestrator 先做 mode 决策：
   - auto + session_id + semantic_set_id -> mixed
   - 仅 session_id -> episodic
   - 仅 semantic_set_id -> semantic
3. episodic 分支：
   - embed query
   - Kùzu 查 Derivative 节点（可按 session_id）
   - `sqlite_vec.search_top_k` 相似度召回
   - Derivative -> Episode 回溯
   - context_window 做邻近 episode 扩展
4. semantic 分支：
   - 先在 SQLite 按 set/category/tag 过滤候选 feature ids
   - 再做向量召回与重排
5. orchestrator 合并 results（episodic+semantic）并附 `short_term_context`。

涉及文件：
- `src/memlite/orchestrator/memory_orchestrator.py`
- `src/memlite/episodic/search.py`
- `src/memlite/semantic/service.py`
- `src/memlite/storage/semantic_feature_store.py`

## 4) 删除链路

### 删除 episodic（DELETE /memories/episodes）
1. orchestrator 调 `EpisodicDeleteService`。
2. 标记 SQLite episode deleted。
3. 删除 derivative 向量索引。
4. 删除 Kùzu Episode/Derivative 节点。
5. 清理 semantic history/citation/orphan features。

### 删除 semantic（DELETE /memories/semantic）
1. 直接走 `semantic_service.semantic_delete()`。
2. 支持按 ids 或 set/category/tag 过滤删除。

涉及文件：
- `src/memlite/episodic/delete.py`
- `src/memlite/orchestrator/memory_orchestrator.py`
- `src/memlite/storage/semantic_feature_store.py`

## 5) MCP 调用链路

1. `memlite-mcp-stdio/http` -> `mcp/server.py`。
2. 每个 tool 调用前会：`ensure_initialized()` + `authorize(api_key)`。
3. tool 再调用 orchestrator/store（与 REST 共用同一资源图）。
4. 支持上下文记忆：`set_context/get_context`。

涉及文件：
- `src/memlite/mcp/server.py`

---

## 6) 审计中发现的不合理点（待修复）

### P0-1 语义抽取是占位实现（功能名义上有，实质未完成）
- 现状：`BackgroundTaskRunner` 的 processor 为 `_noop_history_processor`，只返回计数，不做真实抽取。
- 风险：`semantic_set_ingested_history` 会被标记已处理，但没有新增 feature，造成“语义记忆已入库”的错觉。
- 位置：`src/memlite/app/background.py`

### P0-2 默认 embedding 为关键词规则向量，召回质量不可用
- 现状：`default_embedder` 固定 4 维关键词桶（food/travel/work/profile）。
- 风险：真实语义检索会严重失真；不同领域 query 几乎不可扩展。
- 位置：`src/memlite/app/resources.py`

### P1-1 `sqlite_vec` 实际是 Python 全表余弦扫描，不是高性能向量引擎
- 现状：`search_top_k` 读取候选 embedding_json，在 Python 里计算 cosine。
- 风险：数据量增大后延迟线性上升；与“sqlite-vec”命名预期不一致。
- 位置：`src/memlite/storage/sqlite_vec.py`

### P1-2 graph 写入未做幂等保护，重复写入可能产生重复节点/边
- 现状：Kùzu `add_nodes` 用 `CREATE`，无 `MERGE`/唯一约束兜底。
- 风险：重复 add 或重放恢复时可能重复图数据。
- 位置：`src/memlite/storage/graph_store.py`

### P1-3 配置接口与执行路径脱钩
- 现状：`/memory-config` 可改 episodic/short-term/long-term 参数，但检索路径多数未消费这些动态配置。
- 风险：用户改配置后行为无变化，易误判。
- 位置：`src/memlite/memory/config_service.py` + orchestrator/search 调用路径

### P2-1 短期记忆上下文构建存在“只取最近5条 episode”的硬编码
- 现状：`_build_short_term_context` 固定 `limit=5` 回填。
- 风险：与 short-term capacity 语义不一致，可能丢上下文。
- 位置：`src/memlite/orchestrator/memory_orchestrator.py`

### P2-2 删除链路先软删再图删，跨存储事务一致性依赖补偿
- 现状：SQLite/Kùzu/sqlite_vec 非同一事务域。
- 风险：中途失败会出现部分删除，需要后续 reconcile 修复。
- 位置：`src/memlite/episodic/delete.py`、`src/memlite/tools/migration.py`

---

## 7) 建议修复顺序

1. **先修 P0**：真实 embedding provider + 真实 semantic ingestion。
2. **再修 P1**：向量检索后端性能与图写幂等。
3. **最后修 P2**：配置生效一致性与上下文策略细节。

## 8) 备注（验证）

本次源码审计后，已用项目虚拟环境跑抽样测试：
- `.venv/bin/pytest -q tests/unit/test_memory_orchestrator.py tests/unit/test_semantic_service.py tests/unit/test_sqlite_vec.py tests/integration/test_memory_orchestrator_integration.py`
- 结果：14 passed
