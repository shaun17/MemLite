# MemLite Schema 设计文档

## 1. 文档目的

本文档定义 MemLite 在 `SQLite + sqlite-vec + Kùzu` 方案下的逻辑数据模型、
物理表结构建议、索引建议和关键查询映射。

目标是为后端开发、存储适配器开发和测试提供统一 schema 基线。

## 2. 设计原则

- 事务主数据优先落在 SQLite
- 图关系优先放在 Kùzu
- 向量数据优先放在 sqlite-vec
- 所有表都应尽量支持幂等写入和可补偿清理
- 逻辑隔离依赖 `org_id / project_id / session_id / set_id`

## 3. SQLite Schema 设计

## 3.1 projects

用于表示租户下的项目空间。

### 字段

- `org_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `description TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### 主键

- `(org_id, project_id)`

### 索引

- `idx_projects_created_at(created_at)`

## 3.2 sessions

用于管理会话级元数据和短期记忆摘要。

### 字段

- `session_key TEXT PRIMARY KEY`
- `org_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `user_id TEXT NULL`
- `agent_id TEXT NULL`
- `group_id TEXT NULL`
- `session_id TEXT NOT NULL`
- `summary TEXT NOT NULL DEFAULT ''`
- `summary_updated_at TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### 索引

- `idx_sessions_org_project(org_id, project_id)`
- `idx_sessions_user(user_id)`
- `idx_sessions_agent(agent_id)`

## 3.3 episodes

存储原始事件记录，是 episodic memory 的事实源。

### 字段

- `uid TEXT PRIMARY KEY`
- `org_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `session_key TEXT NOT NULL`
- `session_id TEXT NOT NULL`
- `producer_id TEXT NOT NULL`
- `producer_role TEXT NOT NULL`
- `produced_for_id TEXT NULL`
- `sequence_num INTEGER NOT NULL DEFAULT 0`
- `episode_type TEXT NOT NULL`
- `content_type TEXT NOT NULL`
- `content TEXT NOT NULL`
- `filterable_metadata_json TEXT NULL`
- `metadata_json TEXT NULL`
- `created_at TEXT NOT NULL`
- `deleted INTEGER NOT NULL DEFAULT 0`

### 外键

- `session_key -> sessions.session_key`

### 索引

- `idx_episodes_session_created(session_key, created_at)`
- `idx_episodes_project_created(org_id, project_id, created_at)`
- `idx_episodes_session_seq(session_key, sequence_num)`
- `idx_episodes_role(producer_role)`
- `idx_episodes_deleted(deleted)`

### 说明

- `filterable_metadata_json` 保存用户可过滤字段
- 高频过滤字段可考虑冗余列，例如：
  - `user_id`
  - `agent_id`
  - `group_id`
- 若这些字段查询频繁，建议升级为独立列

## 3.4 derivative_records

用于保存 derivative 的元数据，与 sqlite-vec 的向量表形成一一对应。

### 字段

- `uid TEXT PRIMARY KEY`
- `episode_uid TEXT NOT NULL`
- `org_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `session_id TEXT NOT NULL`
- `source TEXT NOT NULL`
- `content_type TEXT NOT NULL`
- `content TEXT NOT NULL`
- `embedding_model TEXT NOT NULL`
- `embedding_dimension INTEGER NOT NULL`
- `created_at TEXT NOT NULL`
- `filterable_metadata_json TEXT NULL`
- `deleted INTEGER NOT NULL DEFAULT 0`

### 外键

- `episode_uid -> episodes.uid`

### 索引

- `idx_derivative_episode(episode_uid)`
- `idx_derivative_session(session_id, created_at)`
- `idx_derivative_deleted(deleted)`

## 3.5 semantic_features

结构化语义事实主表。

### 字段

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `org_id TEXT NOT NULL`
- `project_id TEXT NOT NULL`
- `set_id TEXT NOT NULL`
- `category TEXT NOT NULL`
- `tag TEXT NOT NULL`
- `feature_name TEXT NOT NULL`
- `value TEXT NOT NULL`
- `metadata_json TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `deleted INTEGER NOT NULL DEFAULT 0`

### 索引

- `idx_semantic_set(set_id)`
- `idx_semantic_set_category(set_id, category)`
- `idx_semantic_set_category_tag(set_id, category, tag)`
- `idx_semantic_feature_name(feature_name)`
- `idx_semantic_deleted(deleted)`

## 3.6 semantic_citations

表示 feature 与 episode 的引用关系。

### 字段

- `feature_id INTEGER NOT NULL`
- `episode_id TEXT NOT NULL`

### 主键

- `(feature_id, episode_id)`

### 外键

- `feature_id -> semantic_features.id`
- `episode_id -> episodes.uid`

### 索引

- `idx_citations_episode(episode_id)`

## 3.7 set_ingested_history

记录哪些 history message 已经被 semantic ingestion 消费。

### 字段

- `set_id TEXT NOT NULL`
- `history_id TEXT NOT NULL`
- `ingested INTEGER NOT NULL DEFAULT 0`
- `created_at TEXT NOT NULL`

### 主键

- `(set_id, history_id)`

### 索引

- `idx_ingested_set(set_id, ingested)`
- `idx_ingested_created(created_at)`

## 3.8 semantic_config_set_type

### 字段

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `org_id TEXT NOT NULL`
- `org_level_set INTEGER NOT NULL DEFAULT 0`
- `metadata_tags_sig TEXT NOT NULL`
- `name TEXT NULL`
- `description TEXT NULL`

### 唯一约束

- `(org_id, org_level_set, metadata_tags_sig)`

## 3.9 semantic_config_set_id_resources

### 字段

- `set_id TEXT PRIMARY KEY`
- `set_name TEXT NULL`
- `set_description TEXT NULL`
- `embedder_name TEXT NULL`
- `language_model_name TEXT NULL`

## 3.10 semantic_config_set_id_set_type

### 字段

- `set_id TEXT PRIMARY KEY`
- `set_type_id INTEGER NOT NULL`

## 3.11 semantic_config_category

### 字段

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `set_id TEXT NULL`
- `set_type_id INTEGER NULL`
- `name TEXT NOT NULL`
- `prompt TEXT NOT NULL`
- `description TEXT NULL`

### 约束

- `set_id` 与 `set_type_id` 必须二选一
- `(set_id, name)` 唯一
- `(set_type_id, name)` 唯一

## 3.12 semantic_config_tag

### 字段

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `category_id INTEGER NOT NULL`
- `name TEXT NOT NULL`
- `description TEXT NOT NULL`

### 约束

- `(category_id, name)` 唯一

## 3.13 semantic_config_disabled_category

### 字段

- `set_id TEXT NOT NULL`
- `disabled_category TEXT NOT NULL`

### 主键

- `(set_id, disabled_category)`

## 4. sqlite-vec Schema 设计

## 4.1 设计原则

- 向量表不存复杂业务字段
- 只保留主键和 embedding
- 复杂过滤统一在 SQLite 普通表完成

## 4.2 derivative_embedding_vec

### 字段建议

- `derivative_uid TEXT PRIMARY KEY`
- `embedding FLOAT[]`

### 关联关系

- `derivative_uid -> derivative_records.uid`

### 用途

- episodic similarity search

## 4.3 semantic_feature_embedding_vec

### 字段建议

- `feature_id INTEGER PRIMARY KEY`
- `embedding FLOAT[]`

### 关联关系

- `feature_id -> semantic_features.id`

### 用途

- semantic similarity search

## 4.4 向量检索建议模式

### Episodic 检索

1. 生成 query embedding
2. 从 `derivative_embedding_vec` 中取 top-k
3. 回查 `derivative_records`
4. 获取 `episode_uid`
5. 回查 `episodes` 与 Kùzu 图关系

### Semantic 检索

1. 结构化过滤得到候选 feature 集
2. 生成 query embedding
3. 在 `semantic_feature_embedding_vec` 上检索
4. 回查 `semantic_features`
5. 视情况加载 citations

## 5. Kùzu Schema 设计

## 5.1 设计原则

- 共享 schema
- 不按 session 动态建图表
- 使用 `org_id/project_id/session_id` 做逻辑隔离
- 图只保存“关系有价值”的对象

## 5.2 Node：Episode

### 建议属性

- `uid STRING PRIMARY KEY`
- `org_id STRING`
- `project_id STRING`
- `session_key STRING`
- `session_id STRING`
- `timestamp TIMESTAMP`
- `sequence_num INT64`
- `producer_id STRING`
- `producer_role STRING`
- `content STRING`
- `content_type STRING`
- `episode_type STRING`
- `deleted BOOL`

## 5.3 Node：Derivative

### 建议属性

- `uid STRING PRIMARY KEY`
- `episode_uid STRING`
- `org_id STRING`
- `project_id STRING`
- `session_id STRING`
- `timestamp TIMESTAMP`
- `source STRING`
- `content STRING`
- `content_type STRING`
- `embedding_model STRING`
- `deleted BOOL`

## 5.4 Rel：DERIVED_FROM

### 定义

- `FROM Derivative TO Episode`

### 建议属性

- `uid STRING`
- `created_at TIMESTAMP`

## 5.5 可选关系

若后续需要更强图查询能力，可增加：

- `NEXT_IN_SESSION`
- `MENTIONS_TOPIC`
- `REFERENCES_FEATURE`

但在第一版中并非必须。

## 6. 查询模式映射

## 6.1 add_memory

### SQLite

- 插入 `episodes`
- 插入 `derivative_records`

### sqlite-vec

- 插入 derivative 向量

### Kùzu

- 插入 Episode 节点
- 插入 Derivative 节点
- 插入 `DERIVED_FROM` 边

## 6.2 search_episodic

### Step 1

- sqlite-vec：查 `derivative_embedding_vec`

### Step 2

- SQLite：回查 `derivative_records`

### Step 3

- Kùzu：按 derivative -> episode 做关系跳转

### Step 4

- SQLite 或 Kùzu：做上下文扩展

### Step 5

- 应用层：合并去重与 rerank

## 6.3 search_semantic

### Step 1

- SQLite：按 set/category/tag/filter 初筛

### Step 2

- sqlite-vec：做语义近邻召回

### Step 3

- SQLite：回查 `semantic_features`

### Step 4

- SQLite：加载 `semantic_citations`

## 6.4 delete_memory

### SQLite

- 软删除或硬删除 `episodes`
- 删除 `derivative_records`
- 清理 `semantic_citations`
- 清理 `set_ingested_history`

### sqlite-vec

- 删除 derivative / feature 向量

### Kùzu

- 删除相关节点与边

## 7. 索引建议

## 7.1 SQLite 索引优先级

高优先级：

- `episodes(session_key, created_at)`
- `episodes(org_id, project_id, created_at)`
- `derivative_records(episode_uid)`
- `semantic_features(set_id, category, tag)`
- `set_ingested_history(set_id, ingested)`

中优先级：

- `episodes(producer_role)`
- `semantic_features(feature_name)`
- `sessions(org_id, project_id)`

## 7.2 Kùzu 索引优先级

高优先级：

- `Episode.uid`
- `Derivative.uid`
- `Derivative.episode_uid`
- `Episode.session_id`

## 8. 数据一致性策略

## 8.1 写入顺序建议

推荐顺序：

1. SQLite 主记录
2. sqlite-vec 向量写入
3. Kùzu 图写入

原因：

- SQLite 作为事务锚点最稳定
- 向量层和图层可重建

## 8.2 补偿策略

若后续写入失败：

- 记录 repair task
- 后台任务根据 SQLite 主记录重建 vec 和图节点

## 8.3 删除策略

推荐默认：

- SQLite 先软删
- vec / 图异步清理
- 定期 hard delete compact

## 9. 迁移建议

如果已有历史系统数据，需要准备三类导入器：

- episode 导入器
- semantic feature 导入器
- graph relation 导入器

导入顺序建议：

1. projects/sessions
2. episodes
3. derivative_records
4. semantic_features
5. citations
6. sqlite-vec embeddings
7. Kùzu nodes/edges

## 10. 验收标准

Schema 设计若满足以下条件，则可进入实现阶段：

- 所有核心查询都有明确数据落点
- 所有实体都有主键、索引和删除策略
- 向量层与主事务层关联清晰
- 图层职责边界明确
- 迁移顺序明确

## 11. 结论

这套 schema 设计的核心思想是：

- **SQLite 承担主数据与事务能力**
- **sqlite-vec 承担向量召回能力**
- **Kùzu 承担图关系与上下文能力**

三者分工清晰后，系统既能保持长期记忆能力，又能实现单机轻量部署。

