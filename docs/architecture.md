# MemLite 技术架构文档

## 1. 文档目的

本文档定义 MemLite 的目标能力、核心模块、运行链路、数据模型、
存储架构、部署形态和非功能要求。

本文档面向以下读者：

- 架构师
- 后端工程师
- AI / Agent 平台工程师
- 测试工程师
- 运维与平台团队

阅读本文件后，即使此前未接触过相关项目，也应能够理解：

- MemLite 要解决什么问题
- 系统由哪些核心组件组成
- 数据如何流转
- 为什么采用 `Kùzu + SQLite + sqlite-vec`
- 需要满足哪些功能与质量约束

## 2. 问题定义

AI Agent 天生偏“短记忆”。如果缺少持久化记忆层，系统通常会遇到：

- 无法跨会话记住用户偏好、历史事实和执行上下文
- 检索上下文时只能依赖近期消息或临时 prompt
- 历史对话无法结构化沉淀为可复用知识
- 部署需要依赖多种重量级数据库，增加开发和运维复杂度

MemLite 的目标是提供一套轻量、可嵌入、低运维成本的记忆基础设施，
让 AI Agent 具备长期记忆、结构化事实提取和可解释检索能力。

## 3. 总体目标

### 3.1 功能目标

MemLite 必须提供以下能力：

1. **会话级事件记忆（Episodic Memory）**
   - 存储对话消息、事件记录、工具调用摘要等
   - 支持按语义检索历史事件
   - 支持按时间和元数据过滤
   - 支持上下文扩展（向前/向后补充邻近事件）

2. **结构化语义记忆（Semantic / Profile Memory）**
   - 从事件中提取事实、偏好、标签、分类等结构化信息
   - 支持按集合、类别、标签、特征名和值查询
   - 支持向量检索与属性过滤结合

3. **短期工作记忆（Working / Short-term Memory）**
   - 管理当前会话内的近期消息
   - 当消息量超限时自动摘要压缩
   - 为检索与回答提供近期上下文

4. **统一 API 能力**
   - 项目/租户隔离
   - 增删改查 memory
   - 配置 semantic category / tag / set type
   - 健康检查、指标输出、MCP tool 接口

### 3.2 非功能目标

- 单机部署简单，默认仅依赖本地文件
- 资源占用显著低于传统图数据库 + 独立关系数据库方案
- 保持较高的检索一致性与可解释性
- 支持异步 I/O 模型
- 支持未来扩展为远程数据库或分层存储

## 4. 架构总览

MemLite 采用分层架构：

1. **接口层**
   - REST API
   - MCP Server
   - Python / TypeScript SDK

2. **应用编排层**
   - 项目与会话管理
   - Memory 增删改查编排
   - 检索策略与检索代理（Retrieval Agent）

3. **记忆服务层**
   - Short-term Memory
   - Episodic Memory
   - Semantic Memory

4. **资源与基础设施层**
   - Embedding 模型
   - Reranker / 重排序器
   - Language Model
   - 指标与日志

5. **存储层**
   - `Kùzu`：事件图关系与上下文邻接
   - `SQLite`：配置、会话、事件原始记录、结构化元数据
   - `sqlite-vec`：向量索引与相似度检索

## 5. 核心模块设计

### 5.1 Gateway / API Layer

职责：

- 接收外部请求
- 校验输入
- 将请求转发给应用编排层
- 将内部模型转换为 API DTO
- 输出指标、错误码和可观测信息

建议接口：

- `POST /projects/create`
- `POST /projects/get`
- `POST /projects/list`
- `POST /projects/delete`
- `POST /memories/add`
- `POST /memories/search`
- `POST /memories/list`
- `POST /memories/delete`
- `POST /semantic/feature/add`
- `POST /semantic/feature/update`
- `POST /semantic/feature/get`
- `POST /semantic/config/*`
- `GET /health`
- `GET /metrics`

### 5.2 Orchestrator

职责：

- 统一调度各类记忆模块
- 按 `org_id / project_id / user_id / session_id` 建立隔离边界
- 管理查询目标（episodic / semantic / mixed）
- 控制搜索过滤、上下文扩展和结果合并

关键职责拆分：

- Session 生命周期管理
- Episode 写入编排
- Semantic 提取触发
- Search 路由与结果合并
- 删除与级联清理

### 5.3 Short-term Memory

职责：

- 维护当前会话近期消息窗口
- 统计消息长度和容量
- 超限时触发摘要
- 提供当前会话快速上下文

特点：

- 数据量小
- 读写频繁
- 适合优先存于内存并定期持久化到 SQLite

### 5.4 Episodic Memory

职责：

- 管理长期事件记忆
- 将原始事件转换为可检索的 derivative 片段
- 根据 embedding + metadata 召回相关事件
- 执行上下文扩展

Episodic Memory 的关键对象：

- **Episode**：原始事件节点
- **Derivative**：由 Episode 派生出的检索片段
- **Derived-From Edge**：Derivative 到 Episode 的关系

### 5.5 Semantic Memory

职责：

- 从事件历史中抽取结构化事实
- 存储事实条目、标签、类别、集合类型
- 支持按 set / category / tag / feature / value 查询
- 支持语义向量检索与属性过滤

Semantic Memory 的关键对象：

- `set_id`：某一用户/代理/群组维度的事实集合
- `category`：事实类别
- `tag`：类别下的标签
- `feature`：结构化特征项
- `citation`：事实来源到历史事件的引用

### 5.6 Retrieval Agent

职责：

- 将自然语言查询转为检索策略
- 决定只查 episodic、只查 semantic，还是二者混合
- 对查询进行改写、拆分和上下文增强
- 对召回结果做组合与排序

该模块可选，但推荐保留，以减少底层存储变化对上层问答质量的影响。

## 6. 运行链路

### 6.1 写入链路：新增事件记忆

1. 客户端发送 memory add 请求
2. API 校验参数并构建内部 EpisodeEntry
3. Orchestrator 写入 Episode Store（SQLite）
4. Episodic Memory 将 Episode 转换为一个或多个 Derivative
5. Embedder 生成向量
6. Derivative 写入 `sqlite-vec` 对应向量表
7. Episode / Derivative / Edge 关系写入 `Kùzu`
8. 若启用 semantic ingestion，则将 Episode 标记为待抽取
9. Semantic Memory 异步提取结构化特征并写入 SQLite + sqlite-vec

### 6.2 检索链路：查询历史记忆

1. 客户端发送 search 请求
2. Orchestrator 判断目标记忆类型与过滤条件
3. Episodic 检索：
   - Embed query
   - 在 `sqlite-vec` 中检索相似 Derivative
   - 在 `Kùzu` 中获取对应 Episode 与邻接上下文
   - 执行 context expansion
   - 用 reranker 重排
4. Semantic 检索：
   - 若是结构化过滤查询，则优先 SQLite 条件过滤
   - 若是自然语言查询，则 embed query 并在 `sqlite-vec` 中检索 feature
   - 结合 category/tag/set_id 过滤
5. Orchestrator 合并结果并返回

### 6.3 删除链路

1. 接收 episode 或 feature 删除请求
2. 删除 SQLite 中的原始行与关联引用
3. 删除 sqlite-vec 中对应向量
4. 删除 Kùzu 中对应节点与边
5. 清理 semantic citations 和待抽取状态

### 6.4 配置链路

1. 创建或更新 semantic category / tag / set type
2. 写入 SQLite 配置库
3. 根据需要刷新缓存
4. 后续 ingestion 任务自动使用新配置

## 7. 存储架构设计

## 7.1 设计原则

- 事件关系和上下文路径查询交给图数据库
- 配置、事务性元数据和原始记录交给 SQLite
- 向量相似度搜索由 sqlite-vec 承担
- 避免把某一数据库的方言特性暴露到业务层

## 7.2 Kùzu 的职责

Kùzu 用于承载图结构信息：

- Episode 节点
- Derivative 节点
- `DERIVED_FROM` 关系
- 可选的上下文边、引用边、主题边

推荐采用**共享 schema + session_id 列隔离**，而不是按 session 动态建表。

推荐节点模式：

- `Episode(uid, session_id, org_id, project_id, timestamp, source, content, ...)`
- `Derivative(uid, session_id, episode_uid, timestamp, content, ...)`

推荐边模式：

- `DERIVED_FROM(FROM Derivative TO Episode)`

Kùzu 负责：

- 关系追踪
- 邻接遍历
- 上下文扩展
- 节点/边级过滤辅助

## 7.3 SQLite 的职责

SQLite 用于承载事务性和结构化数据：

- 项目与会话元数据
- short-term memory 摘要和状态
- episode 原始存储索引
- semantic feature 主记录
- semantic category / tag / set type 配置
- ingestion 状态与 citations

建议启用：

- WAL 模式
- 外键约束
- 合理索引
- 周期性 `VACUUM` / `ANALYZE`

## 7.4 sqlite-vec 的职责

sqlite-vec 用于承载向量检索：

- Derivative 向量
- Semantic Feature 向量
- 可选 query cache 向量

推荐使用方式：

- 向量单独存储到 vec 表
- 业务主数据仍保留在普通 SQLite 表中
- 通过主键关联完成回表

推荐检索策略：

- **两段式检索**
  1. 先从 SQLite 取候选 ID 集合（按 metadata/filter）
  2. 再从 sqlite-vec 做向量搜索
  3. 必要时在应用层执行二次精排

这样能避免把复杂布尔过滤全部压给向量扩展层。

## 8. 逻辑数据模型

### 8.1 Episode

字段建议：

- `uid`
- `org_id`
- `project_id`
- `session_id`
- `producer_id`
- `producer_role`
- `produced_for_id`
- `content`
- `content_type`
- `episode_type`
- `created_at`
- `sequence_num`
- `filterable_metadata`
- `metadata`

### 8.2 Derivative

字段建议：

- `uid`
- `episode_uid`
- `session_id`
- `created_at`
- `content`
- `content_type`
- `embedding_model`
- `embedding_dimension`

### 8.3 Semantic Feature

字段建议：

- `id`
- `set_id`
- `category`
- `tag`
- `feature_name`
- `value`
- `metadata`
- `created_at`
- `updated_at`
- `embedding_ref`

### 8.4 Citation

字段建议：

- `feature_id`
- `episode_id`

### 8.5 Set Type / Category / Tag

用于定义 semantic extraction 的结构化规则与查询边界。

## 9. 关键查询模式

### 9.1 Episodic Similarity Search

输入：

- query text
- session / project / org 范围
- metadata filter
- top-k
- expand_context

过程：

1. query embedding
2. `sqlite-vec` 查 Derivative 向量近邻
3. 回表获取 Derivative 元数据
4. 通过 Kùzu 找到对应 Episode
5. 执行上下文扩展
6. rerank
7. 输出有序 Episode 列表

### 9.2 Episodic Context Expansion

依赖：

- Kùzu 中的 Episode 节点时间属性
- Episode 邻近关系或按时间排序查询

目标：

- 对命中的核心 Episode 向前/向后补充上下文
- 在 token 预算内优先保留最接近核心事件的消息

### 9.3 Semantic Search

输入：

- query text 或结构化条件
- set_id/category/tag/filter

过程：

- 条件检索时：优先 SQLite
- 语义检索时：embed query -> sqlite-vec -> 回表 -> 过滤 -> 输出
- 若启用 citations，则同时返回出处 Episode

## 10. 资源管理设计

系统需要统一管理以下资源：

- SQL engine（SQLite）
- Kùzu connection / session
- sqlite-vec extension loader
- Embedders
- LLMs
- Rerankers
- Metrics factory

资源管理要求：

- 惰性初始化
- 连接复用
- 生命周期显式管理
- 失败时能够降级或快速报错

## 11. 部署架构

### 11.1 本地开发模式

- 单进程 API 服务
- 本地 SQLite 文件
- 本地 Kùzu 数据目录
- 本地 sqlite-vec 扩展

适合：

- 开发调试
- PoC
- 桌面端内嵌部署

### 11.2 单机服务模式

- 1 个 API 进程
- 1 份 SQLite 数据文件
- 1 份 Kùzu 数据目录
- WAL 模式优化读写并发

适合：

- 小中型内部服务
- 轻量 SaaS 单租户场景

### 11.3 扩展模式

若未来需要多实例部署，可演进为：

- SQLite 仅保留配置与本地缓存
- Semantic/episodic 迁移到远程化存储
- Orchestrator 与 API 保持不变

## 12. 非功能设计

### 12.1 性能

- 小规模和中规模负载下，读性能应足够支撑实时 Agent 检索
- 写路径允许异步 semantic ingestion
- 对大多数请求，search p95 应控制在可交互范围内

### 12.2 可维护性

- 存储接口与业务接口分离
- 每类存储都有明确抽象接口
- 避免业务层直接写数据库方言 SQL

### 12.3 可测试性

- 各存储适配器都可单测
- 检索流程可做 golden-case 对比测试
- 需要端到端验证“新增 -> 提取 -> 检索 -> 删除”链路

### 12.4 可观测性

- 请求日志
- 向量检索耗时
- graph traversal 耗时
- ingestion backlog
- DB 连接与错误计数

### 12.5 数据一致性

- 主事实数据以 SQLite 为事务锚点
- Kùzu 与 sqlite-vec 可采用“事务内顺序写 + 异常补偿”策略
- 删除流程必须支持幂等执行

## 13. 技术选型理由

### 13.1 为什么用 Kùzu

- 适合本地嵌入式图查询场景
- 部署比独立图数据库更轻
- 适合承载 Episode 与 Derivative 的关系查询
- 便于保留图遍历和上下文扩展能力

### 13.2 为什么用 SQLite

- 轻量、成熟、运维成本低
- SQLAlchemy 与异步驱动支持完善
- 适合会话、配置、事实元数据等事务型数据

### 13.3 为什么用 sqlite-vec

- 保持“SQLite 生态内完成向量检索”的轻量目标
- 有利于本地单机部署
- 与 SQLite 回表结合简单

## 14. 架构约束

- 上层 API 和 SDK 语义不能因存储替换而改变
- 存储替换后，核心 Memory 用例必须保持可用
- 不允许将数据库产品特性泄露到业务模型中
- 过滤表达式必须在应用层有统一表示
- 新后端必须支持可重复初始化和幂等清理

## 15. 成功标准

如果以下条件全部满足，则架构目标成立：

- Episodic add/search/list/delete 正常可用
- Semantic feature/category/tag/set type 正常可用
- Mixed retrieval 与 context expansion 行为可用
- MCP / REST / SDK 上层接口无需重写语义
- 单机部署依赖从“多服务”收敛为“嵌入式文件型存储”
- 文档、测试、迁移脚本完整可交付

