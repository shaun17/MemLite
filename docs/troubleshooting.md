# Troubleshooting

## 服务启动失败

检查：

- `MEMOLITE_SQLITE_PATH`
- `MEMOLITE_KUZU_PATH`
- 数据目录是否可写

## 检索无结果

检查：

- 项目和 session 是否已创建
- episodic 数据是否已写入
- `semantic_set_id` 是否与写入时一致
- `mode` 是否选错

## MCP 返回 `unauthorized`

检查：

- 服务端是否配置了 `MEMOLITE_MCP_API_KEY`
- tool 调用是否带了 `api_key`

## OpenClaw 不回忆

检查：

- `autoRecall=true`
- `baseUrl` 指向正确服务
- `searchThreshold` 是否过高
- session 是否一致

## OpenClaw 声称“查了记忆”，但无法证明调用了 MemoLite

这是最容易误判的一类问题。按严重性和概率，通常有以下几种：

1. 模型没有真正调用 tool，只是自然语言声称“我查了”
   验证：
   - 执行 `memolite_status`，确认返回 `provider: "memolite"` 与 `executed: true`
   - 对实际检索调用检查返回体是否含 `provider: "memolite"`、`pluginId: "openclaw-memolite"`
   - 查插件日志里是否出现 `invoked` / `succeeded`

2. 调用了通用 `memory_search`，但路由到了别的 memory provider
   验证：
   - 优先显式调用 `memolite_search` / `memolite_get`
   - 检查 `~/.openclaw/openclaw.json` 中 `plugins.slots.memory` 是否为 `openclaw-memolite`
   - 执行 `openclaw plugins list`

3. MemoLite 插件已安装，但 OpenClaw 没有加载到最新构建产物
   验证：
   - 在 `integrations/openclaw` 下重新执行 `npm run build`
   - 重启 `openclaw gateway`
   - 再跑 `memolite_status`

4. 插件已加载，但后端服务不可达或指错 `baseUrl`
   验证：
   - `curl <baseUrl>/health`
   - `memolite_status` 中 `data.health.status` 必须为 `ok`

5. 检索 tool 真执行了，但 session / org / project 不一致导致查不到目标记忆
   验证：
   - 检查 `orgId` / `projectId` / `userId`
   - 检查 `sessionKey`
   - 对跨会话问题优先使用 `memolite_search` 并显式 `scope=all`

6. 只开启了 `autoRecall`，但用户把“自动注入上下文”误认为“显式执行了 memory_search`
   验证：
   - `autoRecall` 只会触发 `before_agent_start` hook，不等于显式 tool 调用
   - 要验证显式调用，请单独执行 `memolite_search` / `memolite_get`

7. 工具执行失败后被上层用自然语言兜底
   验证：
   - 插件失败时会返回 `{ "error": ... }`
   - 日志会出现 `openclaw-memolite: <tool> failed: ...`
   - 不能把后续模型生成的解释文本当成调用成功证据

## 一次性诊断步骤

```bash
openclaw plugins list
cat ~/.openclaw/openclaw.json
scripts/verify_openclaw_memolite.sh
```

然后在 OpenClaw 内执行：

- `memolite_status`
- `memolite_search {"query":"我喜欢吃什么","scope":"all"}`
- `memolite_get {"id":"<上一条结果中的 uid>"}`

只要这三步的返回里都带有 `provider: "memolite"` 和 `executed: true`，才能认定这次调用链真实经过了 MemoLite。

## 迁移后结果异常

先执行：

```bash
memolite-configure reconcile --output reconcile.json --data-dir ~/.memolite
memolite-configure repair --output repair.json --data-dir ~/.memolite
```

## 测试 warning：`event loop is closed`

当前已知问题：

- 出现在 `aiosqlite` 关闭阶段
- 不影响当前功能正确性
- 已记录在 `docs/full-todo-plan.md`
