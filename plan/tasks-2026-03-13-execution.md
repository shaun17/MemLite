# MemoLite 执行任务清单（非 LLM）

状态说明：`TODO` / `IN_PROGRESS` / `DONE` / `BLOCKED`

- [x] T1 `DONE` 修复 `vector_item_id` CRC32 碰撞风险，并补测试
- [x] T2 `DONE` 建立 embedder provider 抽象（先支持 hash）
- [x] T3 `DONE` 扩展 Settings，加入 embedder provider/model/cache 配置
- [x] T4 `DONE` 在 `resources.py` 中改为通过 factory 注入 embedder，消除硬编码
- [x] T5 `DONE` 修复 `embedder_name` 配置存而不用的问题（先打通全局读取路径）
- [x] T6 `DONE` 引入本地 sentence-transformers embedder（非 LLM）
- [x] T7 `DONE` 增加向量 rebuild/repair 命令骨架
- [x] T8 `DONE` 中文检索链路清理：仅 hash embedder 使用 jieba/fallback hack
- [ ] T9 `IN_PROGRESS` 修复 `rerank_enabled` 假开关问题
- [ ] T10 `TODO` 接入本地 cross-encoder reranker（非 LLM）
- [ ] T11 `TODO` 强化 regex extractor（职业/技能/否定偏好）
- [ ] T12 `TODO` 规则版 query normalization / split
- [ ] T13 `TODO` 启用 sqlite-vec native 检索或预留兼容入口
- [ ] T14 `TODO` 异步 ingestion 并发化与失败隔离

## 执行记录

- 2026-03-13: 初始化任务清单，开始执行 T1。
- 2026-03-13: 完成 T1 `修复 vector_item_id CRC32 碰撞风险，并补测试`；验证：`uv sync --extra dev --python 3.12 && uv run --python 3.12 python -m pytest -q tests/unit/test_derivative_pipeline.py` 通过（4 passed）。
- 2026-03-13: 开始执行 T2 `建立 embedder provider 抽象（先支持 hash）`。
- 2026-03-13: 完成 T2 `建立 embedder provider 抽象（先支持 hash）`；新增 `src/memolite/embedders/` 与 `tests/unit/test_embedders.py`，验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_embedders.py tests/unit/test_derivative_pipeline.py` 通过（7 passed）。
- 2026-03-13: 开始执行 T3 `扩展 Settings，加入 embedder provider/model/cache 配置`。
- 2026-03-13: 完成 T3 `扩展 Settings，加入 embedder provider/model/cache 配置`；验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_config.py tests/unit/test_embedders.py` 通过（4 passed）。
- 2026-03-13: 开始执行 T4 `在 resources.py 中改为通过 factory 注入 embedder，消除硬编码`。
- 2026-03-13: 完成 T4 `在 resources.py 中改为通过 factory 注入 embedder，消除硬编码`；新增 `tests/unit/test_resources.py`，验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_resources.py tests/unit/test_embedders.py tests/unit/test_config.py` 通过（5 passed）。
- 2026-03-13: 开始执行 T5 `修复 embedder_name 配置存而不用的问题（先打通全局读取路径）`。
- 2026-03-13: 完成 T5 `修复 embedder_name 配置存而不用的问题（先打通全局读取路径）`；资源初始化现在会读取 SQLite 中全局唯一的 `embedder_name` 作为 provider override，验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_resources.py tests/unit/test_config.py tests/unit/test_embedders.py` 通过（7 passed）。
- 2026-03-13: 开始执行 T6 `引入本地 sentence-transformers embedder（非 LLM）`。
- 2026-03-13: 完成 T6 `引入本地 sentence-transformers embedder（非 LLM）`；新增可选依赖组 `embeddings` 与 `SentenceTransformerEmbedderProvider`，验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_embedders.py tests/unit/test_resources.py tests/unit/test_config.py` 通过（9 passed）。
- 2026-03-13: 开始执行 T7 `增加向量 rebuild/repair 命令骨架`。
- 2026-03-13: 完成 T7 `增加向量 rebuild/repair 命令骨架`；新增 `rebuild-vectors` CLI 与 `rebuild_vectors_snapshot()`，并顺手修复 migration 对 BLOB 向量存储的兼容问题（export/import、semantic rebuild、snapshot 覆盖 derivative vectors）；验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_cli.py tests/integration/test_migration_tools.py` 通过（9 passed）。
- 2026-03-13: 开始执行 T8 `中文检索链路清理：仅 hash embedder 使用 jieba/fallback hack`。
- 2026-03-13: 完成 T8 `中文检索链路清理：仅 hash embedder 使用 jieba/fallback hack`；背景语义抽取现在仅在 hash provider 下使用中文 overlap hack，`test_tokenizer.py` 迁移到 `embedders.hash_embedder`；验证：`uv run --python 3.12 python -m pytest -q tests/unit/test_background_tasks.py tests/unit/test_tokenizer.py tests/unit/test_embedders.py` 通过（24 passed）。
- 2026-03-13: 开始执行 T9 `修复 rerank_enabled 假开关问题`。
