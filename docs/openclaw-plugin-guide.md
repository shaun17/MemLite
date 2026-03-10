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
- `memolite_search`
- `memory_store`
- `memolite_store`
- `memory_get`
- `memolite_get`
- `memory_list`
- `memolite_list`
- `memory_forget`
- `memolite_forget`
- `memolite_status`

其中 `memory_*` 为兼容通用 memory 工具生态的名称，`memolite_*` 为同功能别名，用于让 OpenClaw/Agent 在多记忆插件场景里明确选择 MemoLite。`memolite_status` 用于验证当前调用链是否真的到达 MemoLite 插件与后端服务。

## 自动行为

### `autoCapture`

在 agent 结束后把消息写入 MemLite。

### `autoRecall`

在 agent 启动前根据 prompt 做检索，并把结果注入上下文。

## 调试

- 查看 OpenClaw 插件日志
- 先确认 `baseUrl` 可访问
- 再确认项目和 session 是否存在

## 严格验证是否真的调用了 MemoLite

按下面顺序验证，能把“模型口述”和“真实调用”区分开：

1. 先执行 `memolite_status`
   返回结果必须包含：
   - `provider: "memolite"`
   - `pluginId: "openclaw-memolite"`
   - `executed: true`
   - `data.health.status: "ok"`

2. 检查检索类 tool 的返回包络
   `memory_search` / `memolite_search` / `memory_get` / `memolite_get` 成功时现在都会返回：
   - `provider: "memolite"`
   - `pluginId: "openclaw-memolite"`
   - `tool: "<实际调用的 tool 名称>"`
   - `executed: true`

3. 查看插件日志
   每次真正执行都会记录：
   - `openclaw-memolite: <tool> invoked session=...`
   - `openclaw-memolite: <tool> succeeded session=...`
   如果只有模型回复，没有这两类日志，就不能认定 MemoLite 被调用过。

4. 多 memory provider 场景优先显式使用 `memolite_*`
   如果同时装了别的 memory 插件，优先调用 `memolite_search` / `memolite_get`，不要只依赖通用名 `memory_search` / `memory_get`。

静态侧可以先跑：

```bash
scripts/verify_openclaw_memolite.sh
```
