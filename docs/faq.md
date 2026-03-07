# FAQ

## `MemLite` 适合什么场景？

适合本地开发、单机部署、轻量级 Agent 记忆层。

## 是否必须安装 `sqlite-vec` 原生扩展？

不是。当前实现有 Python fallback。

## 是否支持 REST、MCP、SDK 同时接入？

支持。它们共用同一套资源管理和存储层。

## 是否适合高并发多实例写入？

不是当前主目标。当前更偏向单机和轻量部署。

## 数据迁移怎么做？

使用：

- `memlite-configure export`
- `memlite-configure import`
- `memlite-configure reconcile`
- `memlite-configure repair`

## OpenClaw 插件是否已经可用？

可用。支持：

- `memory_search`
- `memory_store`
- `memory_get`
- `memory_list`
- `memory_forget`
- `autoCapture`
- `autoRecall`
