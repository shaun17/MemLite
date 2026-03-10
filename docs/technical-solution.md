# MemLite 技术方案文档

## 1. 背景

现有长期记忆系统通常采用：

- 图数据库承载 episodic memory 的关系结构与上下文查询
- 关系数据库承载配置、元数据和 semantic memory 主记录
- 向量扩展承载 embedding 检索

这类架构功能完整，但在本地开发、轻量部署和边缘场景下存在问题：

- 依赖组件多
- 部署复杂
- 运维成本高
- 资源占用高
- 本地体验不够友好

因此需要设计一套轻量替代方案，将底层存储统一收敛为：

- `Kùzu`：图关系层
- `SQLite`：事务与配置层
- `sqlite-vec`：向量检索层

目标是在轻量化的同时，保持核心能力不变。

## 2. 方案目标

### 2.1 必须保持的能力

- 跨会话事件记忆
- 结构化语义记忆
- 过滤查询
- 上下文扩展
- 向量检索
- 重排序
- 会话摘要
- 统一 REST / MCP / SDK 接口

### 2.2 轻量化目标

- 单机即可运行
- 降低本地开发与测试门槛
- 减少外部服务依赖
- 降低容器和 CI 环境复杂度

### 2.3 迁移约束

- 上层调用协议不变
- 业务模型尽量不变
- 允许底层 adapter 和数据模型重写
- 允许检索内部实现从“数据库内完成”变为“应用层组合完成”

## 3. 存储替换策略

## 3.1 替换总览

| 能力域 | 原方案 | 新方案 | 迁移方式 |
|---|---|---|---|
| 图关系与上下文扩展 | Neo4j | Kùzu | 重写 `VectorGraphStore` 适配层 |
| 事务数据与配置 | PostgreSQL | SQLite | 保持 SQLAlchemy 抽象，替换连接配置 |
| 向量检索 | pgvector | sqlite-vec | 新建向量存储实现 |
| 配置存储 | PostgreSQL | SQLite | 直接兼容或少量改造 |
| Episode Store | PostgreSQL / SQLite | SQLite | 统一到 SQLite |
| Session Store | PostgreSQL / SQLite | SQLite | 统一到 SQLite |

## 3.2 原则

- **接口不变，适配器替换**
- **共享 schema，不使用按 session 动态建表**
- **先过滤后向量检索，必要时应用层精排**
- **主事务数据先写 SQLite，图与向量层做同步写入或补偿**

## 4. 详细方案设计

### 4.1 Episodic Memory 方案

#### 4.1.1 核心思路

将 episodic memory 拆成三份数据：

1. **Episode 原始记录**：SQLite
2. **Derivative 向量索引**：sqlite-vec
3. **Episode / Derivative 图关系**：Kùzu

#### 4.1.2 为什么不直接只用 SQLite

虽然 SQLite 可以承载大量结构化数据，但以下能力更适合图层：

- Derivative 到 Episode 的关系跳转
- 邻接上下文扩展
- 后续扩展引用链、主题链、会话链

因此保留 Kùzu 作为图关系层能更好保留 episodic memory 的语义结构。

#### 4.1.3 新数据组织方式

不按 session 动态创建图 collection，而是统一建模：

- 所有 Episode 进入同一类节点表
- 所有 Derivative 进入同一类节点表
- 所有关系进入同一类边表
- 用 `org_id/project_id/session_id` 做逻辑隔离

优势：

- Kùzu schema 稳定
- 易于迁移和维护
- 便于做全局索引和统计

#### 4.1.4 检索实现

**写入**

- 写 SQLite episode 表
- 生成 derivative 文本
- 生成 embedding
- 写 sqlite-vec derivative 向量表
- 写 Kùzu 节点与边

**查询**

- query embedding
- sqlite-vec 召回 derivative top-k
- 根据 derivative id 回查 episode uid
- Kùzu 获取 episode 关系与邻近上下文
- 应用层执行 rerank 和去重合并

#### 4.1.5 上下文扩展实现

上下文扩展可采用两种方式：

- 方式 A：Kùzu 按时间属性和关系查询邻接节点
- 方式 B：SQLite 中按 `session_id + timestamp + uid` 查询上下文窗口

建议：

- 首选 SQLite 做时间邻域扩展，稳定且实现简单
- Kùzu 保留关系跳转能力，用于未来复杂图检索

这样可以降低对图数据库查询特性的强耦合。

### 4.2 Semantic Memory 方案

#### 4.2.1 核心思路

Semantic memory 分为两层：

- **主记录层**：SQLite
- **向量层**：sqlite-vec

其中：

- `feature`、`citation`、`set_ingested_history` 存 SQLite
- feature embedding 存 sqlite-vec

#### 4.2.2 为什么不继续依赖 PostgreSQL 风格实现

传统方案常依赖：

- `JSONB`
- `pgvector`
- PostgreSQL 特定 migration / index 能力

这些能力迁移到 SQLite 后不再天然存在，最佳做法不是“兼容模拟所有方言”，
而是**新建一个符合 SQLite/sqlite-vec 习惯的存储实现**。

#### 4.2.3 建议表结构

普通表：

- `feature`
- `citation`
- `set_ingested_history`
- `semantic_config_*`

向量表：

- `feature_embedding_vec`
  - `feature_id`
  - `embedding`

#### 4.2.4 检索策略

对于 semantic search，采用三种模式：

1. **结构化过滤模式**
   - 完全使用 SQLite 条件查询
2. **向量召回模式**
   - sqlite-vec 检索后回表
3. **混合模式**
   - SQLite 先筛候选 feature_id
   - sqlite-vec 在候选范围内检索或应用层重排

### 4.3 Session / Episode / Config 方案

这些模块保留 SQLAlchemy 抽象，统一切换到 SQLite：

- SessionDataManager -> SQLite
- EpisodeStore -> SQLite
- SemanticConfigStore -> SQLite

配套建议：

- 使用 `aiosqlite`
- 开启 WAL
- 外键约束 `PRAGMA foreign_keys=ON`
- 为常用过滤字段建立组合索引

## 5. 关键实现改造点

## 5.1 新增适配器

需要新增以下实现：

- `KuzuVectorGraphStore`
- `SqliteVecSemanticStorage`
- `SqliteVecEpisodeIndex`（可选，若将 derivative 向量逻辑单独抽象）
- `SqliteResourceBootstrapper`（可选，统一初始化 SQLite pragma 与扩展加载）

## 5.2 重构资源管理器

资源管理器需要从“按数据库类型硬编码选择”调整为：

- 根据配置显式选择 backend
- graph backend 与 sql backend 分开管理
- semantic storage backend 与 config storage backend 可独立配置

建议配置示例：

```yaml
resources:
  graph_store: kuzu_default
  relational_store: sqlite_default
  semantic_store: sqlite_vec_default
```

## 5.3 改造配置模型

建议新增清晰配置项：

- `graph_backend: kuzu`
- `relational_backend: sqlite`
- `vector_backend: sqlite_vec`
- `kuzu.path`
- `sqlite.path`
- `sqlite_pragma.*`
- `sqlite_vec.extension_path`

## 5.4 改造 VectorGraphStore 实现策略

现有抽象可以保留，但实现策略建议调整：

- collection / relation 参数仅作为逻辑命名，不直接映射为物理 schema
- 在适配器内部统一解析为：
  - node type
  - edge type
  - namespace/session_id/project_id

这样可以保证同一套上层接口继续可用。

## 6. 兼容性评估

## 6.1 能保持不变的部分

- API DTO
- SDK 接口语义
- Orchestrator 层的大部分编排逻辑
- Short-term memory
- semantic extraction 流程
- reranker / embedder / LLM 抽象

## 6.2 需要重写的部分

- Neo4j graph store 适配器
- pgvector semantic storage 适配器
- 部分 migration 初始化流程
- 资源选择逻辑
- 向量检索与过滤组合逻辑

## 6.3 可能产生行为差异的部分

- top-k 召回顺序
- filtered vector search 的精度与性能
- 删除后的索引回收时机
- 多进程写入吞吐上限

## 7. 风险分析与规避措施

### 7.1 风险：Kùzu 对动态图模式支持不如图服务型数据库自然

**表现**

- 原有“按 session 建 collection / relation”的方式不适配

**措施**

- 改为共享 schema + namespace 列隔离
- 把动态图命名逻辑收敛到 adapter 内部

### 7.2 风险：sqlite-vec 对复杂过滤组合支持有限

**表现**

- 很难在一个 SQL 中同时完成复杂布尔过滤和近邻搜索

**措施**

- 两段式检索
- 先结构化过滤，再向量召回
- 候选过大时加应用层二次裁剪

### 7.3 风险：SQLite 并发写能力低于 PostgreSQL

**表现**

- 高并发写时锁竞争增加

**措施**

- 单机场景优先
- semantic ingestion 异步化
- 批量写入
- WAL + 合理事务粒度
- 多 worker 模式默认收敛为 1

### 7.4 风险：多存储写入一致性

**表现**

- SQLite、Kùzu、sqlite-vec 之间不是天然分布式事务

**措施**

- 以 SQLite 为主事务源
- 图和向量层采用顺序写入
- 建立补偿任务和幂等写入策略
- 增加一致性修复工具

## 8. 落地实施计划

## 8.1 Phase 1：轻量 SQL 基础收敛

目标：

- Session Store 全部切到 SQLite
- Episode Store 全部切到 SQLite
- Semantic Config Store 统一 SQLite

交付：

- SQLite 初始化脚本
- 统一 SQLAlchemy 配置
- 本地开发模式跑通

## 8.2 Phase 2：Semantic 向量层替换

目标：

- 新建 `SqliteVecSemanticStorage`
- 替换 PostgreSQL + pgvector 的 feature 向量实现

交付：

- feature 表 + vec 表
- add/update/get/delete/search 全链路可用
- semantic ingestion 测试通过

## 8.3 Phase 3：Episodic 图层替换

目标：

- 新建 `KuzuVectorGraphStore`
- 替换原图数据库适配器

交付：

- add_nodes / add_edges / search_similar / search_related / get_nodes / delete_nodes
- episodic add/search/delete 测试通过

## 8.4 Phase 4：运行链路优化

目标：

- 优化两段式检索性能
- 加入缓存与批处理
- 补全 metrics 与 trace

## 8.5 Phase 5：迁移工具与文档

目标：

- 提供旧数据导出 -> 新数据导入工具
- 提供验证脚本
- 输出部署手册

## 9. 测试方案

## 9.1 单元测试

覆盖：

- Kùzu graph store adapter
- sqlite-vec semantic storage
- SQLite config/session/episode store
- filter parser 与 filter compiler

## 9.2 集成测试

覆盖：

- add memory -> search memory
- add memory -> semantic extraction -> semantic search
- delete memory / delete feature
- context expansion
- mixed retrieval

## 9.3 一致性测试

为关键场景准备 golden cases：

- 用户偏好问答
- 跨会话历史召回
- 时间邻域上下文扩展
- semantic category/tag 过滤

评估指标：

- top-k 命中率
- 召回顺序稳定性
- 删除后残留率
- 引用完整性

## 9.4 压测

重点压测：

- 单机会话写入吞吐
- episodic search 延迟
- semantic search 延迟
- ingestion backlog 消化速度

## 10. 运维与部署建议

### 10.1 目录建议

```text
memlite/
  data/
    memolite.sqlite3
    kuzu/
  extensions/
    sqlite-vec.*
  logs/
```

### 10.2 SQLite 建议配置

- `journal_mode=WAL`
- `synchronous=NORMAL`
- `foreign_keys=ON`
- `temp_store=MEMORY`
- 热点查询建立组合索引

### 10.3 备份策略

- SQLite 文件定期快照
- Kùzu 数据目录定期备份
- 配置与 schema 版本纳入版本控制

## 11. 验收标准

满足以下条件即可视为方案成功：

- 新增、检索、删除 episodic memory 全部可用
- semantic feature 全部 CRUD 可用
- category/tag/set type 配置可用
- mixed retrieval 可用
- 单机部署不再依赖独立 Neo4j / PostgreSQL 服务
- 文档、测试、初始化脚本齐备

## 12. 最终建议

本方案适合作为“长期记忆基础设施的轻量版落地形态”。

推荐采用以下实施原则：

- **先统一 SQLite，再替换向量层，再替换图层**
- **先保证行为一致，再做性能优化**
- **优先实现稳定的两段式检索，而不是追求数据库内一步到位**
- **所有存储差异收敛在 adapter 内，不污染业务层**

只要严格执行以上原则，就可以在保持核心能力完整的同时，
把底层依赖收敛到适合本地和轻量部署的技术栈。

