# memoLite

memoLite 是一个面向 AI Agent/LLM 应用的轻量级记忆基础设施。

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

- 配置与初始化：`memolite configure ...`
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

### 方式 A（推荐）：PyPI 安装

```bash
pipx install memolite
# 或
pip install memolite
```

适用：普通用户、生产环境、快速上手。

### 方式 B：源码安装（开发者）

- Python `3.12+`
- 在仓库根目录执行

```bash
git clone https://github.com/shaun17/memoLite.git
cd memoLite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

适用：二次开发、调试、修改源码。

安装后可用命令：

- `memolite`（统一入口，推荐）
- `memolite-mcp-stdio`
- `memolite-mcp-http`

## 2. 初始化配置与本地数据（可选）

`memolite configure ...` 用于“服务外”的配置与数据管理，主要做三件事：

1. `configure`：生成 `.env`（写入服务运行所需配置）
2. `init`：初始化本地数据目录与数据库结构（SQLite/Kùzu）
3. `detect-sqlite-vec`：检测 sqlite-vec 扩展可用性（可选）

```bash
memolite configure configure --output .env --data-dir ~/.memolite
memolite configure init --data-dir ~/.memolite
```

可选：检测 sqlite-vec 扩展

```bash
memolite configure detect-sqlite-vec --extension-path /path/to/sqlite-vec.dylib
```

## 3. 启动服务（可选）

```bash
# 前台模式（开发调试）
MEMLITE_PORT=18731 memolite serve
```

默认地址：`http://127.0.0.1:18731`

> 说明：如果你使用 `memolite openclaw setup`，它会自动安装并启动后台服务，因此第 2、3 步可跳过。

## 4. 服务托管与开机自启（推荐）

> 语义约定：
>
> - `memolite-server`：前台运行，适合开发调试（可惰性 init）
> - `memolite service ...`：后台托管命令（install/enable/disable/start/stop/restart/status/uninstall）
> - 开机自启只在 `install --enable` / `enable` 中显式设置
> - `start/restart` 只影响运行态，不改变自启策略
>
> 统一 CLI：
>
> ```bash
> # 安装服务定义（不自动开机自启）
> memolite service install
>
> # 启用开机自启并立即启动
> memolite service enable
>
> # 或一步完成
> memolite service install --enable
>
> # 生命周期管理
> memolite service start
> memolite service stop
> memolite service restart
> memolite service status
>
> # 关闭开机自启 / 卸载服务定义
> memolite service disable
> memolite service uninstall
> ```
>
> 平台说明：
>
> - macOS: LaunchAgent (`~/Library/LaunchAgents/ai.memolite.server.plist`)
> - Linux: systemd user service (`~/.config/systemd/user/ai.memolite.server.service`)
>
> Linux 如需用户级服务在离线后继续运行，可按需启用 linger：
>
> ```bash
> loginctl enable-linger "$USER"
> ```

## 5. OpenClaw 一键接入（A 方案脚本）

```bash
memolite openclaw setup
```

该脚本会自动执行：

1. `openclaw plugins install <plugin-path>`
2. 写入 `~/.openclaw/openclaw.json` 的 memolite 配置
3. 安装并启用 memolite 后台服务（默认端口 18731）
4. 重启 OpenClaw gateway
5. 健康检查与插件加载检查

可覆盖参数（CLI）：

```bash
memolite openclaw setup \
  --base-url http://127.0.0.1:18731 \
  --org-id openclaw \
  --project-id openclaw \
  --user-id openclaw \
  --auto-capture true \
  --auto-recall true \
  --search-threshold 0.5 \
  --top-k 5
```

参数说明：

- `--base-url`：memolite 服务地址，默认 `http://127.0.0.1:18731`
- `--org-id`：组织标识，用于项目隔离（默认 `openclaw`）
- `--project-id`：项目标识，用于项目级隔离（默认 `openclaw`）
- `--user-id`：用户标识，用于用户级归属（默认 `openclaw`）
- `--auto-capture`：是否自动写入会话记忆（`true/false`）
- `--auto-recall`：是否自动召回相关记忆（`true/false`）
- `--search-threshold`：检索阈值（0~1，越高越严格）
- `--top-k`：每次检索返回的最大候选条数

额外运维子命令：

```bash
# 状态与诊断
memolite openclaw status
memolite openclaw doctor

# 配置查看 / 更新 / 重置
memolite openclaw configure show
memolite openclaw configure set --base-url http://127.0.0.1:18731
memolite openclaw configure reset

# 卸载集成（仅移除 memolite 相关项）
memolite openclaw uninstall --dry-run
memolite openclaw uninstall
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
memolite-mcp-stdio
# 或
memolite-mcp-http
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
memolite configure export --output snapshot.json --data-dir ~/.memolite
memolite configure import --input snapshot.json --data-dir ~/.memolite

# 对账/修复
memolite configure reconcile --output reconcile.json --data-dir ~/.memolite
memolite configure repair --output repair.json --data-dir ~/.memolite

# 搜索基准/压测
memolite configure benchmark-search --output benchmark.json --data-dir ~/.memolite
memolite configure load-test --base-url http://127.0.0.1:18731 --total-requests 200 --concurrency 20
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

memoLite 已具备可运行的端到端原型能力（写入、检索、删除、MCP、SDK、修复工具）。
在生产化前，建议结合你的业务继续增强：

- 更强 embedding/provider 接入
- 更完整语义抽取策略
- 向量检索后端性能优化
- 监控与容量规划
