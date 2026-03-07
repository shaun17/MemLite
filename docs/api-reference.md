# API Reference

## 系统接口

### `GET /health`

返回服务状态。

### `GET /version`

返回服务版本。

### `GET /metrics`

返回当前 metrics 快照。

## 项目接口

### `POST /projects`

创建项目。

请求体：

```json
{
  "org_id": "demo-org",
  "project_id": "demo-project",
  "description": "demo"
}
```

### `GET /projects`

查询项目列表。

参数：

- `org_id`

### `GET /projects/{org_id}/{project_id}`

获取单个项目。

### `GET /projects/{org_id}/{project_id}/episodes/count`

获取项目下 episode 数量。

### `DELETE /projects/{org_id}/{project_id}`

删除项目。

## 会话接口

### `POST /sessions`

创建会话。

### `GET /sessions`

按 `org_id/project_id/user_id/agent_id/group_id` 查询会话。

### `GET /sessions/{session_key}`

获取单个会话。

### `DELETE /sessions/{session_key}`

删除会话。

## Memory 接口

### `POST /memories`

写入 episodic memory。

### `POST /memories/search`

检索 memory。

返回主要字段：

- `mode`
- `rewritten_query`
- `subqueries`
- `episodic_matches`
- `semantic_features`
- `combined`
- `expanded_context`
- `short_term_context`

### `POST /memories/agent`

返回适合 agent 直接消费的聚合上下文。

### `GET /memories`

按 `session_key` 列出记忆。

### `GET /memories/{uid}`

获取单条记忆。

### `DELETE /memories/episodes`

删除 episodic memory。

### `DELETE /memories/semantic`

删除 semantic memory。

## Semantic Feature 接口

### `POST /semantic/features`

创建 feature。

### `GET /semantic/features/{feature_id}`

读取 feature。

### `PATCH /semantic/features/{feature_id}`

更新 feature。

## Semantic Config 接口

前缀：`/semantic/config`

### Set Type

- `POST /set-types`
- `GET /set-types`
- `DELETE /set-types/{set_type_id}`

### Set

- `POST /sets`
- `GET /sets`
- `GET /sets/{set_id}`

### Category

- `POST /categories`
- `GET /categories`
- `GET /categories/{category_id}`
- `GET /categories/{name}/set-ids`
- `DELETE /categories/{category_id}`

### Category Template

- `POST /category-templates`
- `GET /category-templates`

### Disabled Category

- `POST /disabled-categories`
- `GET /disabled-categories/{set_id}`

### Tag

- `POST /tags`
- `GET /tags`
- `DELETE /tags/{tag_id}`

## Memory Config 接口

前缀：`/memory-config`

- `GET /episodic`
- `PATCH /episodic`
- `GET /short-term`
- `PATCH /short-term`
- `GET /long-term`
- `PATCH /long-term`
