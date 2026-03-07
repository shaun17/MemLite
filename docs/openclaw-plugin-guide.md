# OpenClaw Plugin Guide

插件目录：

- `integrations/openclaw`

## 安装

```bash
openclaw plugins install ./MemLite/integrations/openclaw
```

## 配置项

- `baseUrl`
- `orgId`
- `projectId`
- `userId`
- `autoCapture`
- `autoRecall`
- `searchThreshold`
- `topK`

## 推荐配置

```json
{
  "baseUrl": "http://127.0.0.1:8080",
  "orgId": "demo-org",
  "projectId": "demo-project",
  "userId": "demo-user",
  "autoCapture": true,
  "autoRecall": true,
  "searchThreshold": 0.5,
  "topK": 5
}
```

## 提供的 tools

- `memory_search`
- `memory_store`
- `memory_get`
- `memory_list`
- `memory_forget`

## 自动行为

### `autoCapture`

在 agent 结束后把消息写入 MemLite。

### `autoRecall`

在 agent 启动前根据 prompt 做检索，并把结果注入上下文。

## 调试

- 查看 OpenClaw 插件日志
- 先确认 `baseUrl` 可访问
- 再确认项目和 session 是否存在
