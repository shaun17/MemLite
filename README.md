# MemLite

MemLite 是一个面向 AI Agent/LLM 应用的轻量级记忆基础设施。

它把常见的“多数据库重部署”记忆架构，收敛为本地优先的组合：

- **SQLite**：事务数据（projects/sessions/episodes/semantic）
- **Kùzu**：Episode/Derivative 图关系与回溯
- **sqlite-vec 兼容层**：向量检索（当前默认实现为 SQLite + Python fallback）

> 目标：让 Agent 具备可持久、可检索、可扩展的长期记忆能力，同时保持部署简单。

---

## 功能介绍

### 1) Episodic Memory（事件记忆）

- 存储对话事件（episode）
- 自动生成 derivative 片段
- 支持语义检索 + 过滤（角色/类型）
- 支持上下文扩展（前后窗口）

### 2) Semantic Memory（结构化记忆）

- 管理 `set/category/tag/feature` 结构化事实
- 支持向量检索 + 属性过滤
- 支持 citations（事实来源回溯到 episode）
- 支持 set 级配置与禁用分类

### 3) Short-term Memory（短期记忆）

- 会话内短窗口缓存
- 超容量自动摘要压缩
- 检索响应可附带 short-term context

### 4) 接口与集成

- **REST API**（FastAPI）
- **MCP Server**（stdio/http）
- **Python SDK**（内置 client）
- **TypeScript client**（`packages/ts-client`）
- **OpenClaw plugin**（`integrations/openclaw`）

### 5) 运维工具

- 配置与初始化：`memlite-configure`
- 对账/修复：`reconcile` / `repair`
- 搜索基准：`benchmark-search`
- 接口压测：`load-test`

---

## 适用场景

- 本地开发与单机部署的 Agent 记忆层
- 桌面/边缘设备上的轻量记忆服务
- 中小团队内部知识助手
- 对部署复杂度和成本敏感的 AI 应用

---

## 项目结构

```text
src/memlite/
  app/              # 应用启动、资源注入、后台补偿
  api/              # REST 路由与 schema
  orchestrator/     # 统一编排层
  episodic/         # 事件记忆写入/检索/删除
  semantic/         # 语义记忆服务与 session manager
  memory/           # short-term 与 memory-config
  storage/          # SQLite/Kùzu/vector 存储实现
  mcp/              # MCP server
  client/           # Python SDK
  tools/            # benchmark/loadtest/migration
```

---

## 使用方法

## 1. 安装方式

### 方式 A：源码安装（当前可直接使用）

- Python `3.12+`
- 在仓库根目录执行

```bash
git clone https://github.com/shaun17/MemLite.git
cd MemLite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

安装后可用命令：

- `memlite`
- `memlite-server`
- `memlite-configure`
- `memlite-mcp-stdio`
- `memlite-mcp-http`

### 方式 B：PyPI 安装（发布后）

```bash
pipx install memolite
# 或
pip install memolite
```

## 2. 初始化配置与本地数据

## 2. 初始化配置与本地数据

```bash
memlite-configure configure --output .env --data-dir ~/.memlite
memlite-configure init --data-dir ~/.memlite
```

可选：检测 sqlite-vec 扩展

```bash
memlite-configure detect-sqlite-vec --extension-path /path/to/sqlite-vec.dylib
```

## 3. 启动服务

```bash
# 前台模式（开发调试）
MEMLITE_PORT=18731 memlite-server
```

默认建议地址：`http://127.0.0.1:18731`（避免与常见 8080 冲突）

## 4. 服务托管与开机自启（推荐）

> 语义约定：
>
> - `memlite-server`：前台运行，适合开发调试（可惰性 init）
> - `memlite service ...`：后台托管命令（start/stop/restart/status）
> - 开机自启只在 `install --enable` / `enable` 中显式设置
>
> 推荐使用统一 CLI（底层调用 macOS LaunchAgent 脚本）：
>
> ```bash
> # 安装服务定义（不自动开机自启）
> memlite service install
>
> # 启用开机自启并立即启动
> memlite service enable
>
> # 或一步完成
> memlite service install --enable
>
> # 生命周期管理
> memlite service start
> memlite service stop
> memlite service restart
> memlite service status
> ```
>
> （兼容：也可以直接调用 `./scripts/memlite_service.sh ...`）

## 5. OpenClaw 一键接入（A 方案脚本）

```bash
memlite openclaw setup
```

该脚本会自动执行：

1. `openclaw plugins install <plugin-path>`
2. 写入 `~/.openclaw/openclaw.json` 的 memlite 配置
3. 安装并启用 memlite 后台服务（默认端口 18731）
4. 重启 OpenClaw gateway
5. 健康检查与插件加载检查

可覆盖参数（CLI）：

```bash
memlite openclaw setup \
  --base-url http://127.0.0.1:18731 \
  --org-id openclaw \
  --project-id openclaw \
  --user-id openclaw \
  --auto-capture true \
  --auto-recall true \
  --search-threshold 0.5 \
  --top-k 5
```

## 6. 最小调用流程（REST）

### 4.1 创建项目

```bash
curl -X POST http://127.0.0.1:18731/projects \
  -H 'content-type: application/json' \
  -d '{
    "org_id": "demo-org",
    "project_id": "demo-project",
    "description": "quickstart"
  }'
```

### 4.2 创建会话

```bash
curl -X POST http://127.0.0.1:18731/sessions \
  -H 'content-type: application/json' \
  -d '{
    "session_key": "demo-session",
    "org_id": "demo-org",
    "project_id": "demo-project",
    "session_id": "demo-session",
    "user_id": "demo-user"
  }'
```

### 4.3 写入记忆

```bash
curl -X POST http://127.0.0.1:18731/memories \
  -H 'content-type: application/json' \
  -d '{
    "session_key": "demo-session",
    "semantic_set_id": "demo-session",
    "episodes": [
      {
        "uid": "ep-1",
        "session_key": "demo-session",
        "session_id": "demo-session",
        "producer_id": "demo-user",
        "producer_role": "user",
        "sequence_num": 1,
        "content": "Ramen is my favorite food."
      }
    ]
  }'
```

### 4.4 检索记忆

```bash
curl -X POST http://127.0.0.1:18731/memories/search \
  -H 'content-type: application/json' \
  -d '{
    "query": "favorite food",
    "session_key": "demo-session",
    "session_id": "demo-session",
    "semantic_set_id": "demo-session",
    "mode": "mixed"
  }'
```

返回重点字段：

- `episodic_matches`
- `semantic_features`
- `combined`
- `expanded_context`
- `short_term_context`

---

## Python SDK 示例

```python
import asyncio
from memlite.client import MemLiteClient


async def main() -> None:
    async with MemLiteClient(base_url="http://127.0.0.1:18731") as client:
        await client.projects.create(org_id="demo-org", project_id="demo-project")
        await client.memory.add(
            session_key="demo-session",
            episodes=[
                {
                    "uid": "ep-1",
                    "session_key": "demo-session",
                    "session_id": "demo-session",
                    "producer_id": "demo-user",
                    "producer_role": "user",
                    "sequence_num": 1,
                    "content": "Ramen is my favorite food.",
                }
            ],
        )
        result = await client.memory.search(
            query="favorite food",
            session_key="demo-session",
            session_id="demo-session",
        )
        print(result.combined)


asyncio.run(main())
```

完整示例：`examples/python_sdk_quickstart.py`

---

## MCP 使用

### 启动

```bash
memlite-mcp-stdio
# 或
memlite-mcp-http
```

### 常用 tools

- `set_context`
- `add_memory`
- `search_memory`
- `delete_memory`
- `list_memory`
- `get_memory`

详见：`docs/mcp-guide.md`

---

## 常用运维命令

```bash
# 导出/导入
memlite-configure export --output snapshot.json --data-dir ~/.memlite
memlite-configure import --input snapshot.json --data-dir ~/.memlite

# 对账/修复
memlite-configure reconcile --output reconcile.json --data-dir ~/.memlite
memlite-configure repair --output repair.json --data-dir ~/.memlite

# 搜索基准/压测
memlite-configure benchmark-search --output benchmark.json --data-dir ~/.memlite
memlite-configure load-test --base-url http://127.0.0.1:18731 --total-requests 200 --concurrency 20
```

---

## 文档导航

- `docs/quickstart.md`
- `docs/architecture.md`
- `docs/api-reference.md`
- `docs/sdk-usage-guide.md`
- `docs/mcp-guide.md`
- `docs/config-reference.md`
- `docs/deployment-guide.md`
- `docs/troubleshooting.md`
- `docs/faq.md`

---

## 当前状态说明

MemLite 已具备可运行的端到端原型能力（写入、检索、删除、MCP、SDK、修复工具）。
在生产化前，建议结合你的业务继续增强：

- 更强 embedding/provider 接入
- 更完整语义抽取策略
- 向量检索后端性能优化
- 监控与容量规划
