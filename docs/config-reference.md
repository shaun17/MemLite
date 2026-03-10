# Config Reference

## 环境变量总览

### 服务

- `MEMOLITE_HOST`
  - 默认：`127.0.0.1`
- `MEMOLITE_PORT`
  - 默认：`8080`
- `MEMOLITE_APP_NAME`
  - 默认：`MemLite`
- `MEMOLITE_ENVIRONMENT`
  - 默认：`development`
- `MEMOLITE_LOG_LEVEL`
  - 默认：`INFO`

### 存储

- `MEMOLITE_SQLITE_PATH`
  - SQLite 主数据文件路径
- `MEMOLITE_KUZU_PATH`
  - Kùzu 数据目录
- `MEMOLITE_SQLITE_VEC_EXTENSION_PATH`
  - 可选，`sqlite-vec` 原生扩展路径

### MCP

- `MEMOLITE_MCP_API_KEY`
  - 可选
  - 配置后，MCP tool 调用需要传入 `api_key`

### 检索调优

- `MEMOLITE_SEMANTIC_SEARCH_CANDIDATE_MULTIPLIER`
  - 默认：`3`
- `MEMOLITE_SEMANTIC_SEARCH_MAX_CANDIDATES`
  - 默认：`100`
- `MEMOLITE_EPISODIC_SEARCH_CANDIDATE_MULTIPLIER`
  - 默认：`4`
- `MEMOLITE_EPISODIC_SEARCH_MAX_CANDIDATES`
  - 默认：`100`

## `.env` 示例

```env
MEMOLITE_HOST=127.0.0.1
MEMOLITE_PORT=8080
MEMOLITE_SQLITE_PATH=/Users/example/.memolite/memolite.sqlite3
MEMOLITE_KUZU_PATH=/Users/example/.memolite/kuzu
MEMOLITE_LOG_LEVEL=INFO
MEMOLITE_MCP_API_KEY=replace-me
```

## 内存配置 API 默认值

### Episodic

- `top_k`
- `min_score`
- `context_window`
- `rerank_enabled`

### Short-term

- `message_capacity`

### Long-term

- `episodic_enabled`
- `semantic_enabled`

这些配置通过 `/memory-config/*` 接口读写，不直接来自环境变量。
