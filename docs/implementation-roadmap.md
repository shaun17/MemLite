# MemLite 实施路线图

## 1. 文档目的

本文档用于把 MemLite 的技术方案拆解成可执行的实施路径，帮助团队按阶段推进：

- 架构落地
- 存储适配器开发
- 数据迁移
- 测试与验收
- 部署与运维准备

本文档关注的是“怎么做”。

## 2. 总体实施策略

实施策略遵循四条原则：

- **先稳定事务层，再替换向量层，最后替换图层**
- **先保证功能等价，再做性能优化**
- **所有存储差异收敛在 adapter 层**
- **每阶段都必须具备可验证的交付物**

推荐分为 6 个阶段推进。

## 3. Phase 0：项目初始化

### 3.1 目标

建立 MemLite 的最小工程骨架、配置体系和文档体系。

### 3.2 交付物

- 项目目录结构
- 配置文件模板
- 本地启动脚本
- 开发文档与架构文档
- CI 基础脚本

### 3.3 建议目录

```text
memlite/
  src/
    memlite/
      api/
      app/
      common/
      storage/
        sqlite/
        sqlite_vec/
        kuzu/
      memory/
        episodic/
        semantic/
        short_term/
      retrieval/
  tests/
    unit/
    integration/
    e2e/
  docs/
  scripts/
  sample_configs/
```

### 3.4 验收标准

- 项目能成功安装与启动
- 配置文件可加载
- 基础健康检查接口可访问

## 4. Phase 1：SQLite 基础收敛

### 4.1 目标

优先让所有事务性模块统一运行在 SQLite 上。

### 4.2 范围

- Session Store
- Episode Store
- Semantic Config Store
- 基础 migration/初始化逻辑

### 4.3 任务拆分

#### A. SQLite 基础设施

- 封装异步 SQLAlchemy engine 工厂
- 统一执行 SQLite pragma：
  - `journal_mode=WAL`
  - `synchronous=NORMAL`
  - `foreign_keys=ON`
  - `temp_store=MEMORY`
- 实现连接生命周期管理

#### B. Session Store

- 建立 session 表
- 支持 session 创建、读取、删除、更新
- 支持 short-term summary 状态持久化

#### C. Episode Store

- 建立 episode 主表
- 建立 sequence / created_at / session 范围索引
- 支持 episode 新增、查询、删除、分页

#### D. Semantic Config Store

- 建立 set_type / category / tag / disabled categories 表
- 支持 upsert、list、delete
- 确保 SQLite 方言兼容

### 4.4 风险

- SQLite 并发写锁争用
- schema 初始化逻辑不统一

### 4.5 验收标准

- 所有事务性模块在本地单 SQLite 文件上可运行
- Session / Episode / Semantic Config 的 CRUD 全通过
- 单元测试通过

## 5. Phase 2：Semantic 向量层落地

### 5.1 目标

实现基于 `sqlite-vec` 的 semantic memory 存储。

### 5.2 核心产物

- `SqliteVecSemanticStorage`
- feature 主表
- citation 表
- ingestion backlog 表
- feature embedding vec 表

### 5.3 任务拆分

#### A. sqlite-vec 初始化

- 检查扩展可用性
- 封装扩展加载逻辑
- 为测试环境提供 stub 或跳过机制

#### B. Feature 主存储

- 新增 feature 表
- 支持 add/get/update/delete/list
- metadata 使用 JSON 字符串或结构化列存储

#### C. Feature 向量索引

- 建立 `feature_id -> vector` 映射
- 支持 add/update/delete 向量
- 支持 top-k 相似检索

#### D. Citation / History

- 支持 feature 到 episode 的引用
- 支持 history ingestion 状态管理
- 支持按 set_id 获取未抽取消息

#### E. 检索策略

- 结构化过滤：SQLite
- 向量检索：sqlite-vec
- 混合检索：SQLite 先筛候选，应用层或 vec 层补召回

### 5.4 风险

- sqlite-vec 复杂过滤能力有限
- SQLAlchemy 与扩展集成需额外封装

### 5.5 验收标准

- semantic feature 全链路可用
- semantic search 正常工作
- category/tag/set type 配置能参与 semantic 查询

## 6. Phase 3：Kùzu 图层落地

### 6.1 目标

实现基于 Kùzu 的 episodic graph store。

### 6.2 核心产物

- `KuzuVectorGraphStore`
- Kùzu schema 初始化脚本
- Episode / Derivative / DERIVED_FROM 图模型

### 6.3 任务拆分

#### A. 图 schema 设计

- Episode 节点表
- Derivative 节点表
- DERIVED_FROM 关系表
- 必要索引和查询约束

#### B. Adapter 方法实现

必须支持：

- `add_nodes`
- `add_edges`
- `search_related_nodes`
- `get_nodes`
- `search_matching_nodes`
- `delete_nodes`

可选支持：

- `search_directional_nodes`
- 更丰富的 traversal 查询

#### C. 上下文扩展策略落地

建议采用双通道：

- 基础时间邻域：SQLite
- 图关系跳转：Kùzu

#### D. 删除与补偿

- 删除 Episode 时同步清理 Derivative 和图关系
- 失败时进入补偿队列或重试任务

### 6.4 风险

- Kùzu 对动态图 schema 不友好
- 图查询语义与既有实现可能略有差异

### 6.5 验收标准

- episodic add/search/delete 可用
- context expansion 可用
- delete 后无脏关系残留

## 7. Phase 4：应用编排层打通

### 7.1 目标

把新的三层存储整合进统一 Orchestrator。

### 7.2 范围

- Memory Add 链路
- Search 链路
- Delete 链路
- Session 生命周期
- semantic ingestion 触发与消费

### 7.3 任务拆分

- 统一资源注册与生命周期管理
- 打通 episodic + semantic mixed retrieval
- 统一错误模型
- 增加幂等性保障
- 增加初始化和恢复逻辑

### 7.4 验收标准

- 单进程模式下所有主流程可跑通
- API 行为一致
- SDK 无需改语义即可接入

## 8. Phase 5：质量与性能优化

### 8.1 目标

提升可观测性、稳定性和检索性能。

### 8.2 任务拆分

#### A. 观测能力

- 请求级日志
- search latency 指标
- ingestion backlog 指标
- Kùzu / SQLite / vec 错误计数

#### B. 性能优化

- 批量写入 embeddings
- top-k 查询参数调优
- 热点查询缓存
- context expansion 查询优化
- feature / episode 常用过滤字段索引优化

#### C. 一致性修复工具

- SQLite 和 vec 缺失对账
- SQLite 和 Kùzu 缺失对账
- orphan derivative 清理工具

### 8.3 验收标准

- 有稳定 metrics 输出
- 有基础修复脚本
- p95 延迟达到预期范围

## 9. Phase 6：迁移与发布

### 9.1 目标

支持已有数据迁移，并形成正式发布物。

### 9.2 任务拆分

- 旧存储导出工具
- 新存储导入工具
- 数据对账报告
- 部署手册
- 回滚方案

### 9.3 验收标准

- 小规模样本迁移成功
- 迁移后检索结果可接受
- 发布文档完备

## 10. 模块级实现清单

## 10.1 建议优先实现的抽象接口

- `GraphStore`
- `SemanticStorage`
- `EpisodeStore`
- `SessionStore`
- `SemanticConfigStore`
- `VectorIndex`
- `ResourceManager`

## 10.2 建议具体实现

- `SqliteEngineFactory`
- `SqliteSessionStore`
- `SqliteEpisodeStore`
- `SqliteSemanticConfigStore`
- `SqliteVecFeatureIndex`
- `SqliteVecDerivativeIndex`
- `KuzuGraphStore`
- `MemoryOrchestrator`
- `SemanticIngestionWorker`

## 10.3 API 层任务

- 输入 DTO
- 输出 DTO
- 错误码体系
- 健康检查接口
- metrics 接口
- MCP tools 映射

## 11. 建议里程碑

### 里程碑 M1

- SQLite 基础层完成
- Session / Episode / Config 跑通

### 里程碑 M2

- Semantic storage 跑通
- feature search 跑通

### 里程碑 M3

- Kùzu episodic graph 跑通
- episodic retrieval 跑通

### 里程碑 M4

- mixed retrieval 跑通
- e2e 测试通过

### 里程碑 M5

- migration tool 与部署手册完成

## 12. 测试推进计划

### 12.1 单元测试优先级

1. filter expression
2. SQLite stores
3. sqlite-vec index
4. Kùzu graph store
5. orchestrator

### 12.2 集成测试优先级

1. add -> search episodic
2. add -> ingest -> search semantic
3. delete -> verify cleanup
4. mixed retrieval
5. context expansion

### 12.3 回归测试优先级

- SDK 兼容性
- API 返回结构稳定性
- 删除与重建幂等性

## 13. 人员建议

最小配置建议：

- 1 名后端架构/主程
- 1 名存储与检索工程师
- 1 名测试/平台工程师

## 14. 时间建议

若已有成熟基础代码可复用，建议：

- Phase 0-1：1~2 周
- Phase 2：1~2 周
- Phase 3：2~3 周
- Phase 4：1~2 周
- Phase 5-6：1~2 周

总计建议：`6~11 周`。

## 15. 实施结论

MemLite 适合按“先事务层、后向量层、再图层”的顺序实施。

只要坚持以下原则，落地成功率会比较高：

- adapter 隔离
- 双阶段检索
- SQLite 主事务锚点
- Kùzu 共享 schema 设计
- 每阶段都有可验证验收标准

