# MCP Guide

## 启动方式

### stdio

```bash
memlite-mcp-stdio
```

### HTTP

```bash
memlite-mcp-http
```

默认 HTTP 路径：

- `/mcp`

## 可用 tools

- `set_context`
- `get_context`
- `add_memory`
- `search_memory`
- `delete_memory`
- `list_memory`
- `get_memory`

## context 用法

`set_context` 用于设置会话级默认参数：

- `session_key`
- `session_id`
- `semantic_set_id`
- `mode`
- `limit`
- `context_window`

后续 `search_memory`、`list_memory`、`add_memory` 可复用这些默认值。

## auth 用法

如果设置了：

- `MEMLITE_MCP_API_KEY`

则 MCP tool 调用需要传入：

- `api_key`

## 示例

```json
{
  "session_key": "demo-session",
  "session_id": "demo-session",
  "semantic_set_id": "demo-session",
  "mode": "mixed",
  "api_key": "replace-me"
}
```

## 建议

- 对长期运行的 MCP HTTP 服务启用 `MEMLITE_MCP_API_KEY`
- 对同一会话的连续调用先执行 `set_context`
