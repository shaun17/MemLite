# SDK Usage Guide

## Python SDK

入口：

```python
from memlite.client import MemLiteClient
```

### 项目

```python
await client.projects.create(org_id="org-a", project_id="project-a")
project = await client.projects.get(org_id="org-a", project_id="project-a")
projects = await client.projects.list(org_id="org-a")
count = await client.projects.episode_count(org_id="org-a", project_id="project-a")
```

### Memory

```python
uids = await client.memory.add(
    session_key="session-a",
    semantic_set_id="session-a",
    episodes=[...],
)

search = await client.memory.search(
    query="food ramen",
    session_key="session-a",
    session_id="session-a",
    semantic_set_id="session-a",
    mode="mixed",
)

agent = await client.memory.agent(
    query="food ramen",
    session_key="session-a",
    session_id="session-a",
    semantic_set_id="session-a",
)
```

### Config

```python
set_type_id = await client.config.create_set_type(
    org_id="org-a",
    metadata_tags_sig="user",
    name="default",
)
await client.config.configure_set(set_id="session-a", set_type_id=set_type_id)
await client.config.add_category(name="profile", prompt="extract profile", set_id="session-a")
```

## TypeScript SDK

包位置：

- `packages/ts-client`

典型流程：

```ts
import { MemLiteClient } from "@memlite/ts-client";

const client = new MemLiteClient({ baseUrl: "http://127.0.0.1:8080" });
await client.projects.create({ org_id: "org-a", project_id: "project-a" });
```

建议：

- 服务端地址通过环境变量管理
- 在应用层统一处理 HTTP 错误
- 将 `mode`、`limit`、`context_window` 作为显式参数传递
