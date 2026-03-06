# MemLite Optimization Backlog

本文件记录**不影响当前交付完整性**、但值得后续迭代继续推进的优化项。

原则：

- 不阻塞当前功能交付
- 不改变现有 API 契约
- 优先做可测量、可回滚的优化

## 1. 查询热点缓存

### 1.1 Session Episodes Cache

- 目标：缓存 `session_key -> episodes`
- 价值：降低 `context expansion` 重复读取开销
- 风险：session 内写后失效策略必须明确
- 建议策略：
  - 只缓存只读查询结果
  - 在 `add/delete/purge episode` 后按 `session_key` 精确失效
  - 限制缓存大小和 TTL

### 1.2 Semantic Candidate Cache

- 目标：缓存 `set_id/category/tag -> feature ids`
- 价值：降低 semantic search 的候选集查询成本
- 风险：feature 更新/删除后需精确失效
- 建议策略：
  - 先做本地进程内缓存
  - 命中只用于候选集裁剪，不改变最终排序

## 2. sqlite-vec 路径优化

- 在原生 `sqlite-vec` 可用时切换到原生检索路径
- 为 Python fallback 与原生路径建立统一回归基线
- 评估大候选集下的内存占用与延迟分布

## 3. Top-K 与召回参数精调

- 基于真实数据调优：
  - `semantic_search_candidate_multiplier`
  - `semantic_search_max_candidates`
  - `episodic_search_candidate_multiplier`
  - `episodic_search_max_candidates`
- 输出建议参数区间，而不是只保留默认值

## 4. 批量写入继续优化

- semantic feature 批量写入接口
- derivative 批量落盘与批量 graph 写入
- 大批量导入时的分批大小调优

## 5. SQLite / Kùzu 稳定性收口

- 收口测试环境 `aiosqlite` 关闭阶段 `event loop closed` 警告
- 评估 Kùzu 查询重试的退避策略
- 增加启动恢复与补偿任务的运行上限保护

## 6. 性能与容量评估

- 建立更大的基准数据集
- 输出不同数据规模下的：
  - episodic search latency
  - semantic search latency
  - graph query latency
  - vector query latency
- 形成单机容量建议

## 7. 可选后续项

- 热路径对象池/连接复用进一步评估
- 更细粒度 metrics 标签
- 更完整的 profiling 脚本
