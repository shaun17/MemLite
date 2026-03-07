# Migration Guide

## 目标

将一个 `MemLite` 实例的数据迁移到新的数据目录。

## 导出

```bash
memlite-configure export --output snapshot.json --data-dir ~/.memlite
```

导出内容包含：

- projects
- sessions
- episodes
- semantic config
- semantic features
- citations
- history ingestion 状态

## 导入

```bash
memlite-configure import --input snapshot.json --data-dir ~/.memlite-new
```

导入后会自动重建：

- sqlite 向量表
- derivative 图节点
- derivative 向量索引

## 对账

```bash
memlite-configure reconcile --output reconcile.json --data-dir ~/.memlite-new
```

重点检查：

- `missing_embedding_feature_ids`
- `missing_derivative_vector_ids`
- `missing_episode_graph_nodes`
- `orphan_*`

## 修复

```bash
memlite-configure repair --output repair.json --data-dir ~/.memlite-new
```

修复内容包括：

- orphan 数据清理
- semantic vector 重建
- derivative graph/vector 重建

## 验证

建议迁移后至少执行：

- 一次 `/memories/search`
- 一次 `reconcile`
- 一次 benchmark 或 smoke test
