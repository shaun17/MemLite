# MemLite

MemLite 是一个面向 AI Agent 与 LLM 应用的轻量级长期记忆系统方案。

目标是在保持以下核心能力不变的前提下，将传统的
`Neo4j + PostgreSQL/pgvector` 方案替换为
`Kùzu + SQLite + sqlite-vec`：

- 跨会话持久化记忆
- 对话事件（episodic memory）存储与检索
- 用户事实/偏好（semantic/profile memory）提取与检索
- 记忆过滤、上下文扩展、重排序
- REST API / MCP / SDK 等上层接口保持稳定
- 本地化、单机化、轻量部署能力增强

## 文档目录

- `docs/architecture.md`：系统架构文档
- `docs/technical-solution.md`：技术方案与实施计划
- `docs/full-todo-plan.md`：开发任务与状态跟踪

## Python SDK Quickstart

```python
import asyncio

from memlite.client import MemLiteClient


async def main() -> None:
    async with MemLiteClient(base_url="http://127.0.0.1:8080") as client:
        await client.projects.create(org_id="demo-org", project_id="demo-project")
        projects = await client.projects.list(org_id="demo-org")
        print(projects)


asyncio.run(main())
```

完整示例见 `examples/python_sdk_quickstart.py`。

## 初始化工具

- 生成示例配置：`memlite-configure sample-config --output .env.example`
- 生成实际配置：`memlite-configure configure --output .env --data-dir ~/.memlite`
- 初始化本地存储：`memlite-configure init --data-dir ~/.memlite`
- 检测 `sqlite-vec`：`memlite-configure detect-sqlite-vec --extension-path /path/to/sqlite-vec.dylib`

## 迁移与修复工具

- 导出快照：`memlite-configure export --output snapshot.json --data-dir ~/.memlite`
- 导入快照：`memlite-configure import --input snapshot.json --data-dir ~/.memlite`
- 对账报告：`memlite-configure reconcile --output reconcile.json --data-dir ~/.memlite`
- 修复导数图与向量：`memlite-configure repair --output repair.json --data-dir ~/.memlite`

## 适用场景

- 本地开发与单机部署
- 桌面应用或边缘设备上的 Agent 记忆层
- 中小规模团队内部知识助手
- 对部署成本、运维复杂度和资源占用敏感的 AI 应用

## 核心设计原则

- 上层接口稳定，底层存储可替换
- 业务能力不缩水，内部实现允许重构
- 优先单进程/单机优化，再考虑多实例扩展
- 数据模型统一，避免强绑定某一数据库特性
- 检索质量优先，必要时采用“两段式召回 + 精排”策略
