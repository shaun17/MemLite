# Deployment Guide

## 部署模式

`MemLite` 当前面向：

- 本地开发
- 单机服务
- 轻量级内网部署

不以多实例分布式写入为主目标。

## 目录规划

建议为数据准备独立目录：

```text
~/.memolite/
├── memolite.sqlite3
└── kuzu/
```

## 环境变量

最小部署需要：

```bash
MEMOLITE_HOST=127.0.0.1
MEMOLITE_PORT=8080
MEMOLITE_SQLITE_PATH=/absolute/path/memolite.sqlite3
MEMOLITE_KUZU_PATH=/absolute/path/kuzu
```

可选：

```bash
MEMOLITE_SQLITE_VEC_EXTENSION_PATH=/path/to/sqlite-vec.dylib
MEMOLITE_MCP_API_KEY=replace-me
MEMOLITE_SEMANTIC_SEARCH_CANDIDATE_MULTIPLIER=3
MEMOLITE_SEMANTIC_SEARCH_MAX_CANDIDATES=100
MEMOLITE_EPISODIC_SEARCH_CANDIDATE_MULTIPLIER=4
MEMOLITE_EPISODIC_SEARCH_MAX_CANDIDATES=100
```

## 初始化

```bash
memolite-configure configure --output .env --data-dir ~/.memolite
memolite-configure init --data-dir ~/.memolite
```

## 启动 API

```bash
memolite-server
```

## 启动 MCP

stdio:

```bash
memolite-mcp-stdio
```

HTTP:

```bash
memolite-mcp-http
```

## 健康检查

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/version
curl http://127.0.0.1:8080/metrics
```

## 备份

推荐使用快照命令而不是直接复制运行中的文件：

```bash
memolite-configure export --output snapshot.json --data-dir ~/.memolite
```

恢复：

```bash
memolite-configure import --input snapshot.json --data-dir ~/.memolite
```

## 生产建议

- 为 SQLite 数据文件使用本地磁盘
- 为 Kùzu 数据目录使用稳定路径
- 定期导出 `snapshot.json`
- 将 `reports/` 输出保存到独立目录
- 若启用 MCP HTTP，配置 `MEMOLITE_MCP_API_KEY`
