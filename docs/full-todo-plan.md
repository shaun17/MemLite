# MemLite 全量 TODO Plan

## 1. 文档目标

本文档用于定义 MemLite 的全量交付计划，目标是：

- 以 `Kùzu + SQLite + sqlite-vec` 为底层技术栈
- 完整实现长期记忆系统所需的全部现有能力
- 不遗漏接口、SDK、插件、配置、测试、迁移、运维与发布环节
- 为项目管理、排期、研发拆解和测试验收提供统一基线

本文档按“功能全覆盖 + 工程可交付 + 测试必覆盖”的标准编写。

## 2. 交付原则

- 所有用户可见能力都必须纳入范围
- 所有新增能力必须有对应测试项
- 没有现成测试的模块必须补测试
- 每个阶段都有明确验收标准
- 存储替换不能导致外部接口语义缩水
- REST / MCP / SDK / OpenClaw 插件都属于正式交付范围

## 3. 总周期建议

### 3.1 多人团队（2~3 人）

- 总周期建议：`14~18 周`

### 3.2 单人推进

- 总周期建议：`24~32 周`

### 3.3 周期分配建议

- Phase 0-2：3~4 周
- Phase 3-5：4~6 周
- Phase 6-8：4~5 周
- Phase 9-11：3~4 周

## 4. Phase 0：需求冻结与兼容矩阵

### 周期

- `3~5 天`

### TODO

- [ ] 梳理全部对外能力清单
- [ ] 梳理全部内部能力清单
- [ ] 建立功能兼容矩阵
- [ ] 建立 API 兼容矩阵
- [ ] 建立 SDK 兼容矩阵
- [ ] 建立 OpenClaw 插件兼容矩阵
- [ ] 建立 MCP tool 兼容矩阵
- [ ] 明确哪些功能必须 100% 行为兼容
- [ ] 明确哪些功能允许内部实现变化但输出语义不变
- [ ] 冻结第一版范围与验收边界

### 测试 TODO

- [ ] 补一份“最终验收清单”文档
- [ ] 为每一类功能定义验收用例模板

### 交付物

- `feature-compatibility-matrix.md`
- `api-compatibility-matrix.md`
- `sdk-compatibility-matrix.md`
- `acceptance-checklist.md`

### 验收标准

- 所有现有功能都能映射到后续阶段
- 没有“以后再看”的未归属功能

## 当前进展

- 已修复问题：`semantic_feature_store.py` 已改为使用时区感知 UTC 时间，移除了 `datetime.utcnow()` 弃用告警来源。
- 已完成两批基础框架任务：工程目录、配置加载、环境变量支持、日志模块、异常与错误码、资源管理器骨架、抽象存储接口、健康检查、metrics 和测试目录。
- 已使用 Python 3.12 本地虚拟环境完成两批基础测试验证，当前通过 `74` 个测试用例。

## 5. Phase 1：工程骨架与架构实现

### 周期

- `4~6 天`

### TODO

- [x] 初始化工程目录结构
- [x] 建立配置加载模块
- [x] 建立环境变量支持
- [x] 建立统一日志模块
- [x] 建立统一异常模型
- [x] 建立统一错误码模型
- [x] 建立资源管理器骨架
- [x] 建立抽象存储接口
- [x] 建立健康检查最小服务
- [x] 建立 metrics 最小服务
- [x] 建立本地启动脚本
- [x] 建立测试目录结构
- [x] 建立 CI 基础命令

### 测试 TODO

- [x] 增加配置加载单元测试
- [x] 增加环境变量覆盖测试
- [x] 增加日志/异常基础测试
- [x] 增加 health endpoint 测试

### 验收标准

- 项目可安装
- 服务可启动
- 测试框架可运行

## 6. Phase 2：SQLite 事务基础层

### 周期

- `1.5~2 周`

### TODO

#### 6.1 SQLite 基础设施
- [x] 封装异步 SQLite engine 工厂
- [x] 统一设置 `journal_mode=WAL`
- [x] 统一设置 `foreign_keys=ON`
- [x] 统一设置 `synchronous=NORMAL`
- [x] 统一设置 `temp_store=MEMORY`
- [x] 封装 schema 初始化逻辑
- [ ] 封装 migration 逻辑
- [x] 封装事务管理辅助函数

#### 6.2 Project Store
- [x] 实现 create project
- [x] 实现 get project
- [x] 实现 list projects
- [x] 实现 delete project
- [x] 实现 project episode count

#### 6.3 Session Store
- [x] 实现 create session
- [x] 实现 get session
- [x] 实现 delete session
- [x] 实现 update session metadata
- [x] 实现 search sessions
- [x] 实现 short-term summary 持久化

#### 6.4 Episode Store
- [x] 实现 add episode
- [x] 实现 batch add episodes
- [x] 实现 get episodes by ids
- [x] 实现 list episodes
- [x] 实现 delete episodes
- [x] 实现 delete all episodes in session
- [x] 实现 count episodes
- [x] 实现基于 filter 的匹配查询

#### 6.5 Semantic Config Store
- [x] 实现 set type CRUD
- [x] 实现 set_id resource config CRUD
- [x] 实现 category CRUD
- [x] 实现 tag CRUD
- [x] 实现 disabled category CRUD
- [x] 实现 set_id -> set_type 注册逻辑
- [x] 实现继承 category 读取逻辑

### 测试 TODO

#### 单元测试
- [x] SQLite engine 初始化测试
- [ ] migration 初始化测试
- [x] Project Store CRUD 测试
- [x] Session Store CRUD 测试
- [x] Session Store summary 持久化测试
- [x] Episode Store CRUD 测试
- [x] Episode filter 测试
- [x] Semantic Config Store CRUD 测试
- [x] 继承 category 逻辑测试

#### 集成测试
- [x] SQLite 文件初始化集成测试
- [x] 多 store 协同读写测试

### 验收标准

- SQLite 作为主事务层完全可用
- 所有事务型基础模块均具备测试覆盖

## 7. Phase 3：Short-term Memory

### 周期

- `4~6 天`

### TODO

- [x] 实现短期消息窗口
- [x] 实现容量统计
- [x] 实现消息长度统计
- [x] 实现 overflow 检测
- [x] 实现自动摘要触发
- [x] 实现 summary 持久化
- [x] 实现 close/reset
- [x] 实现恢复已有 summary
- [x] 实现删除单条 episode
- [x] 实现当前上下文读取

### 测试 TODO

#### 单元测试
- [x] add messages 测试
- [x] capacity overflow 测试
- [x] summarize trigger 测试
- [x] summary restore 测试
- [x] delete episode 测试
- [x] close/reset 测试

#### 集成测试
- [x] session store + short-term memory 集成测试

### 验收标准

- short-term memory 全链路可用
- 摘要逻辑与持久化稳定

## 8. Phase 4：Semantic Memory + sqlite-vec

### 周期

- `1.5~2.5 周`

### TODO

#### 8.1 sqlite-vec 基础
- [x] 扩展加载器实现
- [x] 扩展可用性检测
- [x] 向量表初始化逻辑
- [x] top-k 查询封装
- [x] 批量写入封装

#### 8.2 Semantic Feature 主存储
- [x] 实现 add_feature
- [x] 实现 get_feature
- [x] 实现 update_feature
- [x] 实现 delete_features
- [x] 实现 get_feature_set
- [x] 实现 delete_feature_set
- [x] 实现按 filter 查询 feature
- [x] 实现分页 feature 查询

#### 8.3 Citations / History
- [x] 实现 add_citations
- [x] 实现 get_history_messages
- [x] 实现 get_history_messages_count
- [x] 实现 add_history_to_set
- [x] 实现 delete_history
- [x] 实现 mark_messages_ingested
- [x] 实现 get_history_set_ids
- [x] 实现 get_set_ids_starts_with

#### 8.4 Semantic Service
- [x] 实现 semantic ingestion worker
- [x] 实现默认 category 注入逻辑
- [x] 实现 set_id config 选择逻辑
- [x] 实现 feature embedding 生成
- [x] 实现 semantic search
- [x] 实现 semantic list
- [x] 实现 semantic delete

#### 8.5 Semantic Session Manager
- [x] 实现 set_type 管理
- [x] 实现 category 管理
- [x] 实现 category template 管理
- [x] 实现 tag 管理
- [x] 实现 disable category
- [x] 实现 set 绑定/配置逻辑

### 测试 TODO

#### 单元测试
- [x] sqlite-vec 初始化测试
- [x] feature CRUD 测试
- [x] feature vector add/update/delete 测试
- [x] citation CRUD 测试
- [x] history ingestion 状态测试
- [x] semantic config 参与检索测试
- [x] set/category/tag 管理测试

#### 集成测试
- [x] add message -> semantic ingestion -> search 测试
- [x] semantic list/delete 测试
- [x] citations 返回正确性测试

#### 回归测试
- [x] 结构化过滤语义不变测试
- [x] vector search top-k 稳定性测试

### 验收标准

- semantic memory 全量能力实现
- 测试覆盖 CRUD、ingestion、search、delete 全链路

## 9. Phase 5：Episodic Memory + Kùzu

### 周期

- `2~3 周`

### TODO

#### 9.1 Kùzu 基础
- [x] Kùzu 数据目录初始化
- [x] Kùzu schema 初始化
- [x] 连接/会话管理
- [x] 统一图查询封装

#### 9.2 Graph Store
- [x] 实现 add_nodes
- [x] 实现 add_edges
- [x] 实现 get_nodes
- [x] 实现 search_related_nodes
- [x] 实现 search_matching_nodes
- [x] 实现 search_directional_nodes
- [x] 实现 delete_nodes

#### 9.3 Derivative 流程
- [x] 实现 episode -> derivative 派生
- [x] 实现 sentence chunking
- [x] 实现 derivative metadata 映射
- [x] 实现 derivative vector 写入 sqlite-vec
- [x] 实现 derivative graph 写入 Kùzu

#### 9.4 Episodic Search
- [x] 实现 query embedding
- [x] 实现 derivative similarity search
- [x] 实现 derivative -> episode 回查
- [x] 实现 context expansion
- [x] 实现 rerank
- [x] 实现 dedupe + unify
- [x] 实现 score threshold
- [x] 实现 metadata filter

#### 9.5 Episodic Delete
- [x] 实现 delete episodes
- [x] 实现 delete matching episodes
- [x] 实现 delete session episodic memory
- [x] 实现清理 derivative 向量
- [x] 实现清理 graph 节点与边

### 测试 TODO

#### 单元测试
- [x] Kùzu 初始化测试
- [x] graph add/get/delete 测试
- [x] derivative 派生测试
- [x] sentence chunking 测试
- [x] episodic similarity search 测试
- [x] filter + search 测试
- [x] context expansion 测试
- [x] delete cleanup 测试

#### 集成测试
- [x] add episodic -> search 测试
- [x] search + expand_context 测试
- [x] delete episode -> verify no residue 测试

#### 回归测试
- [x] episodic 返回结构稳定性测试
- [x] chronology 排序稳定性测试

### 验收标准

- episodic memory 全量能力实现
- 检索、扩展、删除行为与预期一致

## 10. Phase 6：统一编排层与 Mixed Retrieval

### 周期

- `1~1.5 周`

### TODO

- [x] 实现统一 orchestrator
- [x] 打通 project/session/episode/semantic 生命周期
- [x] 实现 mixed retrieval
- [x] 实现 agent mode
- [x] 实现 short-term + long-term 组合检索
- [x] 实现 episode delete 触发 semantic cleanup
- [x] 实现 project delete 级联清理
- [x] 实现 session delete 级联清理
- [x] 实现 retrieval policy 决策
- [x] 实现 query rewrite / split 策略接口

### 测试 TODO

#### 单元测试
- [x] orchestrator 路由决策测试
- [x] mixed retrieval 合并测试
- [x] delete cleanup 协同测试
- [x] project/session 级联删除测试

#### 集成测试
- [x] mixed retrieval e2e 测试
- [x] agent mode 返回测试
- [x] episodic + semantic 联合搜索测试

### 验收标准

- 编排层功能齐全
- mixed retrieval 可稳定运行

## 11. Phase 7：REST API 全量兼容

### 周期

- `1~1.5 周`

### TODO

#### 项目接口
- [x] create project
- [x] get project
- [x] list projects
- [x] delete project
- [x] get episode count

#### memory 接口
- [x] add memories
- [x] search memories
- [x] list memories
- [x] delete episodic memories
- [x] delete semantic memories

#### semantic feature 接口
- [x] add feature
- [x] get feature
- [x] update feature

#### semantic set / config 接口
- [x] create semantic set type
- [x] list semantic set types
- [x] delete semantic set type
- [x] get semantic set id
- [x] list semantic set ids
- [x] configure semantic set

#### category / tag 接口
- [x] get semantic category
- [x] add semantic category
- [x] add semantic category template
- [x] list semantic category templates
- [x] disable semantic category
- [x] get semantic category set ids
- [x] delete semantic category
- [x] add semantic tag
- [x] delete semantic tag

#### episodic config 接口
- [x] get episodic memory config
- [x] configure episodic memory
- [x] get short-term memory config
- [x] configure short-term memory
- [x] get long-term memory config
- [x] configure long-term memory

#### system 接口
- [x] health
- [x] metrics
- [x] version

### 测试 TODO

#### 单元测试
- [ ] DTO 校验测试
- [ ] 错误映射测试
- [ ] filter 参数解析测试

#### API 测试
- [x] 所有 REST 路由成功路径测试
- [x] 所有 REST 路由错误路径测试
- [ ] 鉴权/无鉴权模式测试
- [x] OpenAPI 生成测试

#### 回归测试
- [ ] 返回 JSON 结构兼容测试
- [x] HTTP 状态码兼容测试

### 验收标准

- REST API 全量可用
- 所有路由有测试

## 12. Phase 8：MCP 全量兼容

### 周期

- `4~6 天`

### TODO

- [x] stdio 模式实现
- [x] http 模式实现
- [x] 生命周期管理
- [x] tool 注册
- [ ] context/auth 注入
- [x] tool schema 校验
- [x] tool 错误处理

### 必须支持的 tool

- [x] add memory
- [x] search memory
- [x] delete memory
- [x] list memory（如纳入范围）
- [x] get memory（如纳入范围）

### 测试 TODO

- [x] stdio tool 调用测试
- [x] http tool 调用测试
- [x] tool 参数校验测试
- [x] tool 错误路径测试
- [x] 生命周期初始化/释放测试

### 验收标准

- MCP stdio/http 均可用
- 所有 tool 均有测试覆盖
- 当前进展：`79` 个测试通过

## 13. Phase 9：Python SDK

### 周期

- `4~6 天`

### TODO

- [x] client 实现
- [x] project 实现
- [x] memory 实现
- [x] config 实现
- [x] error 模型
- [x] retries
- [x] context manager
- [x] 示例代码
- [x] 文档补全

### 测试 TODO

- [x] client 初始化测试
- [x] project CRUD 测试
- [x] memory add/search/list/delete 测试
- [x] retry 测试
- [x] error handling 测试
- [x] integration complete 测试

### 验收标准

- Python SDK 全量可用
- 示例脚本可执行
- 当前进展：`86` 个测试通过

## 14. Phase 10：TypeScript SDK

### 周期

- `4~6 天`

### TODO

- [ ] client 实现
- [ ] project 实现
- [ ] memory 实现
- [ ] types 定义
- [ ] error handler
- [ ] retry 逻辑
- [ ] build 配置
- [ ] docs 生成
- [ ] 使用示例

### 测试 TODO

- [ ] client 测试
- [ ] project 测试
- [ ] memory 测试
- [ ] error handler 测试
- [ ] type surface 稳定性测试
- [ ] build/test 脚本 CI 测试

### 验收标准

- TypeScript SDK build/test 全通过
- npm 包可交付

## 15. Phase 11：OpenClaw 插件

### 周期

- `4~6 天`

### TODO

- [ ] 插件配置 schema
- [ ] local install 支持
- [ ] memory_search
- [ ] memory_store
- [ ] memory_forget
- [ ] memory_get
- [ ] memory_list
- [ ] autoRecall
- [ ] autoCapture
- [ ] UI hints / openclaw.plugin.json
- [ ] 文档说明

### 测试 TODO

- [ ] 插件配置解析测试
- [ ] search/store/forget/get/list 测试
- [ ] autoRecall 测试
- [ ] autoCapture 测试
- [ ] OpenClaw 本地安装 smoke test
- [ ] 插件错误路径测试

### 验收标准

- OpenClaw 本地安装可用
- autoRecall/autoCapture 生效

## 16. Phase 12：CLI、安装与初始化

### 周期

- `3~5 天`

### TODO

- [ ] `memlite-server`
- [ ] `memlite-mcp-stdio`
- [ ] `memlite-mcp-http`
- [ ] `memlite-configure`
- [ ] 配置向导
- [ ] SQLite 初始化命令
- [ ] Kùzu 初始化命令
- [ ] sqlite-vec 检测命令
- [ ] 本地 data 目录初始化
- [ ] 示例配置生成

### 测试 TODO

- [ ] CLI 参数测试
- [ ] CLI 初始化测试
- [ ] 配置写回测试
- [ ] 新机器初始化 smoke test

### 验收标准

- 新环境可快速初始化
- CLI 行为稳定

## 17. Phase 13：迁移工具、对账与修复工具

### 周期

- `1~1.5 周`

### TODO

#### 17.1 迁移工具
- [ ] projects 导出
- [ ] sessions 导出
- [ ] episodes 导出
- [ ] semantic features 导出
- [ ] citations 导出
- [ ] config 导出
- [ ] SQLite 导入
- [ ] sqlite-vec 重建
- [ ] Kùzu 重建

#### 17.2 对账工具
- [ ] SQLite ↔ sqlite-vec 对账
- [ ] SQLite ↔ Kùzu 对账
- [ ] orphan derivative 检测
- [ ] missing graph edge 检测
- [ ] missing embedding 检测

#### 17.3 修复工具
- [ ] 重建 derivative 向量
- [ ] 重建 graph 节点/边
- [ ] 清理 orphan 数据
- [ ] 清理 soft delete residue

### 测试 TODO

- [ ] 迁移小样本测试
- [ ] 对账工具正确性测试
- [ ] 修复工具幂等性测试
- [ ] 迁移后检索可用性测试

### 验收标准

- 数据可迁移
- 对账与修复工具可用

## 18. Phase 14：性能、稳定性、可观测性

### 周期

- `1 周`

### TODO

#### 性能
- [ ] 批量 embedding 写入优化
- [ ] top-k 查询参数调优
- [ ] filter 前置优化
- [ ] context expansion 优化
- [ ] 常用查询索引调优
- [ ] 热点缓存评估与实现

#### 稳定性
- [ ] 幂等写入
- [ ] 幂等删除
- [ ] 重试机制
- [ ] 后台补偿任务
- [ ] 崩溃恢复逻辑

#### 可观测性
- [ ] access log
- [ ] error log
- [ ] search latency 指标
- [ ] ingestion backlog 指标
- [ ] vec query latency 指标
- [ ] graph query latency 指标
- [ ] repair queue 指标

### 测试 TODO

- [ ] 压测脚本
- [ ] 基准测试脚本
- [ ] 幂等性测试
- [ ] 重试/补偿逻辑测试
- [x] metrics 暴露测试

### 验收标准

- 有性能数据
- 有稳定性测试
- 有观测能力

## 19. Phase 15：最终测试、文档与发布

### 周期

- `1~1.5 周`

### TODO

#### 测试总收口
- [ ] 运行全部单元测试
- [ ] 运行全部集成测试
- [ ] 运行全部 e2e 测试
- [ ] 运行回归测试
- [ ] 运行 OpenClaw 集成测试
- [ ] 运行 MCP 集成测试
- [ ] 运行 SDK 集成测试
- [ ] 运行迁移与修复测试
- [ ] 运行性能基准测试

#### 文档
- [ ] Quickstart
- [ ] Deployment Guide
- [ ] Config Reference
- [ ] API Reference
- [ ] SDK Usage Guide
- [ ] MCP Guide
- [ ] OpenClaw Plugin Guide
- [ ] Migration Guide
- [ ] Troubleshooting
- [ ] FAQ

#### 发布
- [ ] changelog
- [x] versioning
- [ ] release build
- [ ] smoke test
- [ ] 发布说明

### 验收标准

- 文档齐备
- 所有测试通过
- 可发布

## 20. 功能全覆盖验收清单

### A. 项目与会话
- [x] create project
- [x] get project
- [x] list projects
- [x] delete project
- [ ] episode count
- [ ] create session
- [ ] get session
- [ ] delete session
- [ ] search sessions

### B. Episodic Memory
- [ ] add episode(s)
- [ ] list episodic memory
- [ ] search episodic memory
- [ ] get episodic memory
- [ ] delete episodic memory
- [ ] delete session episodic memory
- [ ] metadata filter
- [ ] score threshold
- [ ] rerank
- [ ] context expansion
- [ ] sentence chunking

### C. Short-term Memory
- [ ] add messages
- [ ] capacity control
- [ ] summarize
- [ ] restore summary
- [ ] delete episode
- [ ] close/reset

### D. Semantic Memory
- [x] add feature
- [x] get feature
- [x] update feature
- [ ] delete feature(s)
- [ ] list/search feature set
- [ ] delete feature set
- [ ] citations
- [ ] history ingestion
- [ ] mark ingested
- [ ] set id search
- [ ] set ids startswith

### E. Semantic Config
- [ ] create set type
- [ ] list set types
- [ ] delete set type
- [ ] configure set
- [ ] get set config
- [ ] add category
- [ ] add category template
- [ ] list category templates
- [ ] get category
- [ ] disable category
- [ ] delete category
- [ ] add tag
- [ ] update tag
- [ ] delete tag

### F. Retrieval / Agent Mode
- [ ] episodic only
- [ ] semantic only
- [ ] mixed retrieval
- [ ] query rewrite
- [ ] query split
- [ ] agent mode response
- [ ] short-term + long-term merge

### G. REST API
- [ ] 所有项目接口
- [ ] 所有 memory 接口
- [ ] 所有 semantic 接口
- [ ] 所有 config 接口
- [x] health
- [x] metrics
- [x] version

### H. MCP
- [ ] stdio
- [ ] http
- [ ] add/search/delete tools
- [ ] 生命周期管理

### I. Python SDK
- [ ] client
- [ ] project
- [ ] memory
- [ ] retries
- [ ] error handling

### J. TypeScript SDK
- [ ] client
- [ ] project
- [ ] memory
- [ ] types
- [ ] error handling

### K. OpenClaw
- [ ] local install
- [ ] config schema
- [ ] autoCapture
- [ ] autoRecall
- [ ] search/store/forget/get/list

### L. CLI / Tooling
- [ ] server CLI
- [ ] mcp CLI
- [ ] configure CLI
- [ ] bootstrap tools
- [ ] migration tools
- [ ] repair tools

## 21. 测试全覆盖验收清单

### 单元测试
- [ ] config
- [ ] stores
- [ ] filters
- [ ] short-term memory
- [ ] semantic storage
- [ ] graph storage
- [ ] orchestrator
- [ ] DTO / validators
- [ ] SDK helpers

### 集成测试
- [ ] API + SQLite
- [ ] API + sqlite-vec
- [ ] API + Kùzu
- [ ] episodic add/search/delete
- [ ] semantic ingest/search/delete
- [ ] mixed retrieval
- [ ] MCP tools
- [ ] OpenClaw plugin

### E2E 测试
- [x] create project -> add memory -> search -> delete
- [ ] add memory -> semantic ingestion -> recall
- [ ] session close/reopen -> summary restore
- [ ] plugin autoCapture -> autoRecall

### 回归测试
- [ ] API response schema
- [ ] SDK response schema
- [ ] 搜索排序稳定性
- [ ] 过滤语义稳定性
- [ ] 删除后无残留

### 非功能测试
- [ ] 性能基准
- [ ] 压测
- [ ] 幂等性
- [ ] 补偿机制
- [ ] 崩溃恢复
- [ ] 迁移一致性

## 22. 最终结论

MemLite 的完整交付不是单一“存储替换”任务，而是一次：

- 数据层替换
- 检索链路重建
- 对外接口兼容
- 工程测试补齐
- 工具链补齐
- 发布能力补齐

本 TODO 文档已将功能、测试、迁移、发布全部纳入，适合作为项目总计划和迭代拆解基线。
