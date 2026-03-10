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
