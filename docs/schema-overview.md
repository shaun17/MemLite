# MemLite 数据表关系总览（ER 简图 + 表说明）

> 目标：快速理解 `memolite.sqlite3` 里的核心表、关系、读写链路。

## 1. ER 简图（逻辑）

```text
projects (org_id, project_id)
   └── sessions (session_key, org_id, project_id, summary...)
         └── episodes (uid, session_key, session_id, content...)

episodes
   └── derivative_feature_vectors (feature_id=hash(derivative_uid), embedding_json)

semantic_features (id, set_id, category, tag, feature_name, value...)
   ├── semantic_feature_vectors (feature_id -> semantic_features.id)
   └── semantic_citations (feature_id -> semantic_features.id, episode_id -> episodes.uid)

semantic_set_ingested_history (set_id, history_id=episode_id, ingested)
   └── 语义抽取待处理/已处理队列

semantic_config_set_type
semantic_config_set_id_resources (set_id)
semantic_config_set_id_set_type (set_id -> set_type_id)
semantic_config_category (set_id/set_type_id)
semantic_config_category_template (set_type_id)
semantic_config_tag (category_id)
semantic_config_disabled_category (set_id, disabled_category)
```

---

## 2. 表分组与用途

## A. 业务主数据

### `projects`
- 用途：项目维度主表（租户/项目边界）
- 关键字段：
  - `org_id`, `project_id`（联合主键）
  - `description`, `created_at`, `updated_at`

### `sessions`
- 用途：会话主表
- 关键字段：
  - `session_key`（主键）
  - `org_id`, `project_id`, `session_id`
  - `user_id`, `agent_id`, `group_id`
  - `summary`, `summary_updated_at`（short-term 摘要落盘位置）

### `episodes`
- 用途：episodic long-term 原始事件
- 关键字段：
  - `uid`（主键）
  - `session_key`, `session_id`
  - `producer_id`, `producer_role`
  - `sequence_num`, `content`, `content_type`, `episode_type`
  - `metadata_json`, `filterable_metadata_json`
  - `deleted`（软删）

---

## B. 向量检索数据

### `derivative_feature_vectors`
- 用途：episodic derivative 向量索引表
- 关键字段：
  - `feature_id`（整数主键，来自 derivative uid 的稳定映射）
  - `embedding_json`
- 来源：`DerivativePipeline` 写入

### `semantic_feature_vectors`
- 用途：semantic feature 向量索引表
- 关键字段：
  - `feature_id`（FK -> `semantic_features.id`）
  - `embedding_json`

---

## C. 语义记忆主数据

### `semantic_features`
- 用途：结构化语义事实
- 关键字段：
  - `id`（主键）
  - `set_id`（语义集合）
  - `category`, `tag`, `feature_name`, `value`
  - `metadata_json`
  - `deleted`（软删）

### `semantic_citations`
- 用途：事实来源追溯（feature -> episode）
- 关键字段：
  - `feature_id`（FK -> `semantic_features.id`）
  - `episode_id`（对应 `episodes.uid`）
- 主键：`(feature_id, episode_id)`

### `semantic_set_ingested_history`
- 用途：语义抽取队列表（是否 ingest 完成）
- 关键字段：
  - `set_id`
  - `history_id`（通常是 episode uid）
  - `ingested`（0/1）
  - `created_at`

---

## D. 语义配置中心（`semantic_config_*`）

### `semantic_config_set_type`
- 用途：定义 set 类型（模板级）
- 关键字段：`id`, `org_id`, `metadata_tags_sig`, `org_level_set`, `name`

### `semantic_config_set_id_resources`
- 用途：具体 set 的资源配置
- 关键字段：`set_id`, `embedder_name`, `language_model_name`, `set_name`

### `semantic_config_set_id_set_type`
- 用途：set 与 set_type 的映射
- 关键字段：`set_id`, `set_type_id`

### `semantic_config_category`
- 用途：类别定义（可挂 set 或 set_type）
- 关键字段：`id`, `set_id`, `set_type_id`, `name`, `prompt`

### `semantic_config_category_template`
- 用途：类别模板
- 关键字段：`id`, `set_type_id`, `name`, `category_name`, `prompt`

### `semantic_config_tag`
- 用途：类别下 tag 定义
- 关键字段：`id`, `category_id`, `name`, `description`

### `semantic_config_disabled_category`
- 用途：某 set 禁用的 category 列表
- 关键字段：`set_id`, `disabled_category`

---

## 3. 典型读写链路（对应表）

## 写入记忆（POST /memories）
1. 写 `episodes`
2. 生成 derivative 向量 -> 写 `derivative_feature_vectors`
3. 若带 `semantic_set_id` -> 写 `semantic_set_ingested_history`
4. short-term 摘要更新 -> 回写 `sessions.summary`

## 语义抽取补偿（后台）
1. 从 `semantic_set_ingested_history` 取 `ingested=0`
2. 提取 feature -> 写 `semantic_features`
3. 写向量 -> `semantic_feature_vectors`
4. 写来源 -> `semantic_citations`
5. 标记 `semantic_set_ingested_history.ingested=1`

## 检索（POST /memories/search）
- episodic：向量命中 `derivative_feature_vectors` + episodes 回溯
- semantic：过滤 `semantic_features` + 向量命中 `semantic_feature_vectors`
- 最后 orchestrator 合并结果

---

## 4. 快速排查 SQL

```sql
-- 最近会话
SELECT session_key, org_id, project_id, summary, updated_at
FROM sessions
ORDER BY updated_at DESC
LIMIT 20;

-- 最近记忆
SELECT uid, session_key, sequence_num, producer_role, content, deleted
FROM episodes
ORDER BY created_at DESC
LIMIT 20;

-- 语义事实
SELECT id, set_id, category, tag, feature_name, value, deleted
FROM semantic_features
ORDER BY id DESC
LIMIT 50;

-- 事实来源追溯
SELECT c.feature_id, c.episode_id
FROM semantic_citations c
ORDER BY c.feature_id DESC
LIMIT 50;

-- 待处理语义队列
SELECT set_id, history_id, ingested, created_at
FROM semantic_set_ingested_history
ORDER BY created_at DESC
LIMIT 50;
```

---

## 5. 备注

- 除 SQLite 外，MemLite 还会把 Episode/Derivative 关系写入 Kùzu（默认 `~/.memolite/kuzu`）。
- 因此排查“为什么搜不到”时，建议同时看：
  - SQLite 数据是否存在
  - Kùzu 图关系是否完整
  - 向量表是否有对应 embedding
