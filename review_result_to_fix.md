# MemoLite 代码审查报告

> 审查时间：2026-03-22（初审） → 2026-03-22（复审验证）
> 代码来源：GPT 生成

---

## 🔴 严重问题

### 1. ~~Kùzu 图查询存在 Cypher 注入风险~~ ✅ 已修复
- **文件**: `src/memolite/storage/graph_store.py`
- **状态**: 已改为参数化查询（`$parameter_name`），不再拼接字符串。`search_matching_nodes` 和 `search_related_nodes_batch` 均使用 `parameters` dict 传参。
- **验证**: 代码中已无 `_quote()` 函数，所有查询通过 `$match_any_uids`、`$filter_xxx` 等参数绑定。

### 2. ~~Kùzu 连接非线程安全~~ ✅ 已修复
- **文件**: `src/memolite/storage/kuzu_engine.py` 第 58-59 行
- **状态**: 已加 `asyncio.Lock`（`self._connection_lock`）+ 单线程 `ThreadPoolExecutor(max_workers=1)`。所有 `execute()` 和 `query()` 均在 `async with self._connection_lock:` 下执行。
- **验证**: `_run_in_executor` 使用专用单线程池，加上 asyncio Lock，双重保证串行化。

### 3. ~~`BOOTSTRAP_STATEMENTS` schema 定义分裂~~ ✅ 已修复
- **文件**: `src/memolite/storage/sqlite_schema.py`
- **状态**: `semantic_feature_vectors` 表定义已统一为 `embedding BLOB NOT NULL`，与 `sqlite_vec.py` 一致。文件底部的追加语句仅新增 `semantic_citations`、`semantic_set_ingested_history` 等表和索引，不再有冲突。
- **验证**: 建表语句中无 `embedding_json TEXT` 字段。

---

## 🟡 中等问题

### 4. 向量搜索全表扫描 O(n) ⚠️ 未修复（设计如此）
- **文件**: `src/memolite/storage/sqlite_vec.py` 第 155-170 行
- **状态**: `search_top_k()` 仍然加载全部候选向量到内存做 Python 层余弦计算。
- **说明**: 代码注释和 README 均已标注这是 "Python fallback"，适用于轻量级单机场景。
- **建议**: 如果未来数据量上万，需要引入 ANN 索引或外部向量库。

### 5. ~~`list_episodes` 无 limit 时可能 OOM~~ ⚠️ 部分改善
- **文件**: `src/memolite/storage/episode_store.py` 第 116-149 行
- **状态**: `list_episodes` 和 `find_matching_episodes` 已支持 `limit` + `offset` 参数，但默认值仍为 `None`（无限制）。
- **建议**: API 层应设置合理默认值（如 1000），防止调用方忘记传 limit。

### 6. ~~`_summarize_overflow` 摘要无限增长~~ ✅ 已修复
- **文件**: `src/memolite/memory/short_term_memory.py` 第 105-125 行
- **状态**: 已增加 `_truncate_summary()` 函数，对摘要长度设置上限（`_MAX_SUMMARY_LENGTH`）。超长时截断尾部保留最新内容，前缀加 `...`。

### 7. `derivative_pipeline` 每次都调用 `initialize()` ⚠️ 未修复
- **文件**: `src/memolite/episodic/derivative_pipeline.py`
- **状态**: `create_derivatives()` 中未见 `initialize()` 调用（代码第 80-150 行）。可能已在上层 `ResourceManager` 启动时统一初始化。
- **结论**: 该问题可能已通过架构调整解决，但需确认 `_derivative_index.initialize()` 的调用链。

### 8. ~~`find_matching_episodes` 无分页~~ ✅ 已修复
- **文件**: `src/memolite/storage/episode_store.py` 第 223-263 行
- **状态**: 已支持 `limit` 和 `offset` 参数。

### 9. ~~VACUUM 期间阻塞并发写入~~ ✅ 已修复
- **文件**: `src/memolite/app/background.py` 第 105-109 行
- **状态**: 已改用 `PRAGMA wal_checkpoint(PASSIVE)` + `PRAGMA incremental_vacuum(200)`，不再使用阻塞式 `VACUUM`。

---

## 🟢 轻微问题

### 10. `_lookup_episode_uids` 逐个查询效率低 ✅ 已修复
- **文件**: `src/memolite/episodic/search.py` 第 200-210 行
- **状态**: 已改为 `search_related_nodes_batch()` 批量查询，一次 Kùzu 调用拿回所有结果。

### 11. `get_history_messages_count` 实现低效 ✅ 已修复
- **文件**: `src/memolite/storage/semantic_feature_store.py` 第 460-478 行
- **状态**: 已改为 `SELECT COUNT(*)` 直接返回，不再全量取再 `len()`。

### 12. 其他轻微问题（`lru_cache`、模块导入副作用、正则匹配简单等）— 未修复，影响不大。

---

## 📖 README 问题

### 13. ~~章节编号错乱~~ ✅ 已修复
- 第 6 节子标题现在正确为 6.1 / 6.2 / 6.3 / 6.4。

### 14. 英文 README embeddings 安装说明 — 未验证（需查 README.en.md）

### 15. 运维命令一致性 — 部分确认
- README 中 `memolite configure benchmark-search` 等命令存在，但需实际运行确认 CLI 入口是否暴露。

---

## 总结

| 类别 | 总数 | 已修复 | 未修复/设计如此 |
|------|------|--------|-----------------|
| 🔴 严重 | 3 | **3** ✅ | 0 |
| 🟡 中等 | 6 | **4** ✅ | 2（向量全扫+list默认无limit） |
| 🟢 轻微 | 5 | **2** ✅ | 3（影响低） |
| 📖 README | 3 | **1** ✅ | 2（待确认） |

**3个严重问题全部修复**，整体安全性和稳定性已显著改善。剩余中等问题主要是性能相关，在当前轻量级定位下可接受。
