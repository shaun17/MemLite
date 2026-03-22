# MemoLite 模型预加载 + Embedding/Reranker 模型切换

> 创建日期：2026-03-22
> 状态：待执行

---

## 背景

### 问题 1：模型首次调用才下载/加载（冷启动延迟）

当前 `SentenceTransformerEmbedderProvider` 使用惰性加载策略：

```python
# src/memolite/embedders/sentence_transformer.py
def _ensure_model(self):
    if self._model is None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name)  # ← 首次调用时才触发
    return self._model
```

`SentenceTransformer(model_name)` 会做两件事：
1. 如果本地缓存（`~/.cache/huggingface/hub/`）不存在该模型 → 从 HuggingFace Hub 下载（几十 MB ~ 几百 MB）
2. 加载模型到内存并初始化

**调用链：**
```
服务启动
  → ResourceManager.create()
    → create_embedder() → SentenceTransformerEmbedderProvider(model_name=...) # 只存名字
    → provider.as_embedder_fn() → 返回 encode 函数引用                        # 不触发加载
  → resources.initialize() → schema 初始化、recovery 等                        # 不触发加载

用户第一条消息
  → encode(text) → _ensure_model() → SentenceTransformer(name) # ← 这里才加载/下载
```

**后果：** 用户的第一条消息响应时间不可预测（首次可能几十秒等下载），体验差。

### 问题 2：Embedding 模型需更换

当前默认模型 `paraphrase-multilingual-MiniLM-L12-v2`（118MB, 384 维）中文质量一般。
需切换为 `BAAI/bge-small-zh-v1.5`（93MB, 512 维），中文专项优化，速度更快。

### 问题 3：Reranker 未接入

T9（`rerank_enabled` 假开关）已部分修复：`rerank_enabled_getter` 已接入配置读取链路。
但 `reranker: RerankerFn` 参数从未被传入，`_apply_rerank()` 中 `self._reranker is None` 永远为 True。
需要实现一个基于 `BAAI/bge-reranker-base`（278MB）的本地 cross-encoder reranker，并注入到 `EpisodicSearchService`。

---

## 涉及文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/memolite/embedders/sentence_transformer.py` | 修改 | 新增 `warm_up()` 方法 |
| `src/memolite/embedders/base.py` | 修改 | `EmbedderProvider` 新增 `warm_up()` 抽象/默认方法 |
| `src/memolite/embedders/hash_embedder.py` | 修改 | `warm_up()` 空实现 |
| `src/memolite/embedders/factory.py` | 修改 | 默认模型改为 `bge-small-zh-v1.5` |
| `src/memolite/rerankers/` | **新建目录** | reranker 模块 |
| `src/memolite/rerankers/__init__.py` | 新建 | 导出 |
| `src/memolite/rerankers/base.py` | 新建 | `RerankerProvider` 抽象类 |
| `src/memolite/rerankers/cross_encoder.py` | 新建 | `CrossEncoderRerankerProvider` 实现 |
| `src/memolite/rerankers/factory.py` | 新建 | `create_reranker(settings)` 工厂函数 |
| `src/memolite/common/config.py` | 修改 | 新增 reranker 配置字段 |
| `src/memolite/app/resources.py` | 修改 | 启动时 warm_up、注入 reranker |
| `pyproject.toml` | 修改 | `embeddings` 可选依赖组调整 |
| `tests/unit/test_embedders.py` | 修改 | 新增 warm_up 测试 |
| `tests/unit/test_rerankers.py` | 新建 | reranker 单元测试 |
| `tests/unit/test_resources.py` | 修改 | 新增 warm_up + reranker 注入测试 |

---

## 任务拆解

---

### T15：EmbedderProvider 新增 warm_up() 方法

**目标：** 让所有 embedder provider 支持显式预加载，在服务启动阶段调用。

**修改 1：`src/memolite/embedders/base.py`**

在 `EmbedderProvider` 抽象类中新增方法：

```python
async def warm_up(self) -> None:
    """Pre-load model resources during startup.

    Default is no-op. Providers with heavy initialization (model download,
    weight loading) should override this to ensure startup-time loading
    instead of first-request-time loading.
    """
    pass
```

设计决策：
- 用默认空实现而非 `@abstractmethod`，因为 `HashEmbedderProvider` 不需要预加载
- async 方法，因为模型加载可能耗时，不应阻塞事件循环

**修改 2：`src/memolite/embedders/hash_embedder.py`**

无需修改，继承默认空实现即可。

**修改 3：`src/memolite/embedders/sentence_transformer.py`**

新增 `warm_up()` 实现：

```python
async def warm_up(self) -> None:
    """Pre-load the sentence-transformer model into memory.

    Calls _ensure_model() in a thread to avoid blocking the event loop
    during model download / weight loading.
    """
    await asyncio.to_thread(self._ensure_model)
```

关键点：
- 复用已有的 `_ensure_model()` 方法，不引入重复逻辑
- `asyncio.to_thread` 保证模型加载不阻塞事件循环
- 调用后 `self._model` 已初始化，后续 `encode()` 直接命中缓存

**验证方法：**
```bash
uv run --python 3.12 python -m pytest -q tests/unit/test_embedders.py
```

---

### T16：默认 Embedding 模型切换为 bge-small-zh-v1.5

**目标：** 将默认语义 embedding 模型从 `paraphrase-multilingual-MiniLM-L12-v2` 改为 `BAAI/bge-small-zh-v1.5`。

**修改：`src/memolite/embedders/factory.py`**

```python
# 修改前
model_name = settings.embedder_model or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# 修改后
model_name = settings.embedder_model or "BAAI/bge-small-zh-v1.5"
```

**影响范围：**
- 只影响 `embedder_provider == "sentence_transformer"` 且 `embedder_model` 未配置的用户
- 如果用户已在 `.env` 或环境变量中指定 `MEMOLITE_EMBEDDER_MODEL`，不受影响
- `embedder_provider == "hash"` 的用户完全不受影响

**向量维度变化：**
- 旧模型：384 维
- 新模型：512 维
- 维度不兼容 → 切换模型后必须执行 `memolite rebuild-vectors` 重建历史向量（T7 已实现该命令）

**验证方法：**
```bash
uv run --python 3.12 python -m pytest -q tests/unit/test_embedders.py
```
确认 factory 在无 `embedder_model` 配置时返回 `bge-small-zh-v1.5`。

---

### T17：实现 Reranker Provider 抽象层

**目标：** 建立与 embedders 模块对称的 reranker 抽象，支持可插拔的 reranker 后端。

**新建目录结构：**
```
src/memolite/rerankers/
├── __init__.py
├── base.py
├── cross_encoder.py
└── factory.py
```

**新建 1：`src/memolite/rerankers/base.py`**

```python
"""Reranker provider abstractions for MemoLite."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from memolite.episodic.search import EpisodicSearchMatch

# 与 search.py 中已有的 RerankerFn 类型一致
RerankerFn = Callable[[str, list[EpisodicSearchMatch]], Awaitable[list[EpisodicSearchMatch]]]


class RerankerProvider(ABC):
    """Abstract reranker provider contract."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider name for config and diagnostics."""

    @abstractmethod
    async def rerank(
        self, query: str, matches: list[EpisodicSearchMatch]
    ) -> list[EpisodicSearchMatch]:
        """Rerank matches by relevance to query. Return reordered list."""

    async def warm_up(self) -> None:
        """Pre-load model resources during startup. Default is no-op."""
        pass

    def as_reranker_fn(self) -> RerankerFn:
        """Return a function adapter matching existing RerankerFn call sites."""
        return self.rerank
```

设计说明：
- `rerank()` 接收 query + 粗筛结果列表，返回重新排序后的列表
- 入参/出参类型直接使用 `EpisodicSearchMatch`（与 `search.py:15` 的 `RerankerFn` 签名一致）
- `warm_up()` 与 embedder 对称，用于启动预加载
- `as_reranker_fn()` 与 embedder 的 `as_embedder_fn()` 对称，适配现有注入点

**新建 2：`src/memolite/rerankers/__init__.py`**

```python
"""Reranker providers for MemoLite."""

from memolite.rerankers.base import RerankerProvider
from memolite.rerankers.factory import create_reranker

__all__ = ["RerankerProvider", "create_reranker"]
```

**验证方法：**
```bash
uv run --python 3.12 python -c "from memolite.rerankers import RerankerProvider, create_reranker; print('import ok')"
```

---

### T18：实现 CrossEncoderRerankerProvider

**目标：** 基于 `BAAI/bge-reranker-base` 实现本地 cross-encoder reranker。

**新建：`src/memolite/rerankers/cross_encoder.py`**

```python
"""Cross-encoder reranker backed by sentence-transformers CrossEncoder."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from memolite.episodic.search import EpisodicSearchMatch
from memolite.rerankers.base import RerankerProvider


@dataclass(slots=True)
class CrossEncoderRerankerProvider(RerankerProvider):
    """Local cross-encoder reranker.

    Uses sentence-transformers CrossEncoder to score (query, document) pairs.
    Model is lazily loaded on first use, or eagerly via warm_up().
    """

    model_name: str
    _model: object | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return "cross_encoder"

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is not installed; "
                    "install with `pip install memolite[embeddings]`"
                ) from exc
            self._model = CrossEncoder(self.model_name)
        return self._model

    async def warm_up(self) -> None:
        """Pre-load the cross-encoder model into memory."""
        await asyncio.to_thread(self._ensure_model)

    async def rerank(
        self, query: str, matches: list[EpisodicSearchMatch]
    ) -> list[EpisodicSearchMatch]:
        if not matches:
            return matches

        model = self._ensure_model()

        # 构造 (query, document) pair 列表
        # document 来自 episode.content — 即存储的原文
        pairs = [(query, match.episode.content) for match in matches]

        # CrossEncoder.predict() 返回 numpy array of float scores
        scores = await asyncio.to_thread(model.predict, pairs)

        # 将 score 关联回 match，按 score 降序排列
        scored = sorted(
            zip(scores, matches),
            key=lambda item: float(item[0]),
            reverse=True,
        )
        return [match for _, match in scored]
```

**关键设计点：**

1. **模型选择：`BAAI/bge-reranker-base`（278MB）**
   - cross-encoder 架构，对 (query, doc) 做交叉注意力打分
   - 中文质量好，体积适中
   - 与 sentence-transformers 生态一致，无需额外依赖

2. **`episode.content` 作为 rerank 文本**
   - `EpisodicSearchMatch.episode` 是 `EpisodeRecord`，其 `.content` 字段是原始消息内容
   - cross-encoder 需要原文而非 embedding 向量来做精排

3. **线程隔离**
   - `model.predict()` 是 CPU 密集型（涉及模型推理），必须用 `asyncio.to_thread` 避免阻塞事件循环

4. **无需修改 `pyproject.toml`**
   - `sentence-transformers` 已在 `[embeddings]` 可选依赖组中
   - `CrossEncoder` 是 `sentence-transformers` 内置类，无额外包

**需确认 `EpisodeRecord` 字段名：**
```bash
grep -n "content\|class EpisodeRecord" src/memolite/storage/episode_store.py | head -10
```
确认用于 rerank 的文本字段名是 `content` 还是其他名称。

**验证方法：**
```bash
uv run --python 3.12 python -m pytest -q tests/unit/test_rerankers.py
```

---

### T19：实现 Reranker 工厂函数 + 配置字段

**目标：** 通过配置文件控制 reranker 的开关和模型选择。

**修改 1：`src/memolite/common/config.py`**

在 `Settings` 类中新增字段：

```python
# --- Reranker 配置 ---
reranker_provider: str = Field(default="none")
# 可选值：
#   "none" — 不使用 reranker（当前行为）
#   "cross_encoder" — 本地 cross-encoder 模型
reranker_model: str | None = Field(default=None)
# cross_encoder provider 默认使用 BAAI/bge-reranker-base
# 用户可通过 MEMOLITE_RERANKER_MODEL 环境变量覆盖
```

对应环境变量：
- `MEMOLITE_RERANKER_PROVIDER=cross_encoder`
- `MEMOLITE_RERANKER_MODEL=BAAI/bge-reranker-base`

**修改 2：`src/memolite/rerankers/factory.py`**

```python
"""Reranker provider factory."""

from __future__ import annotations

from memolite.common.config import Settings
from memolite.rerankers.base import RerankerProvider


def create_reranker(settings: Settings) -> RerankerProvider | None:
    """Create a reranker provider from settings. Returns None if disabled."""
    provider = getattr(settings, "reranker_provider", "none")
    if provider == "none":
        return None
    if provider == "cross_encoder":
        from memolite.rerankers.cross_encoder import CrossEncoderRerankerProvider
        model_name = settings.reranker_model or "BAAI/bge-reranker-base"
        return CrossEncoderRerankerProvider(model_name=model_name)
    raise ValueError(f"unsupported reranker_provider: {provider}")
```

设计说明：
- 返回 `None` 表示不使用 reranker（保持向后兼容，`reranker_provider` 默认 `"none"`）
- `cross_encoder` 的 import 放在分支内（惰性导入），避免 `sentence-transformers` 未安装时 import error

**`reranker_provider` 与 `rerank_enabled` 的关系：**
- `config_service.py` 中的 `rerank_enabled: bool` 是运行时动态开关（API 可修改）
- `Settings.reranker_provider` 是静态配置（决定用哪个 reranker 实现）
- 两者独立：`reranker_provider=cross_encoder` + `rerank_enabled=False` → 模型加载了但不使用
- 这样设计允许用户通过 API 动态开关 rerank 而不需要重启服务

**验证方法：**
```bash
uv run --python 3.12 python -m pytest -q tests/unit/test_rerankers.py tests/unit/test_config.py
```

---

### T20：resources.py 启动预加载 + 注入 Reranker

**目标：** 在 `ResourceManager.initialize()` 中完成 embedder 和 reranker 的模型预加载，并将 reranker 注入 `EpisodicSearchService`。

**修改：`src/memolite/app/resources.py`**

**变更点 1：`ResourceManager` dataclass 新增字段**

```python
from memolite.rerankers import create_reranker
from memolite.rerankers.base import RerankerProvider
from memolite.embedders.base import EmbedderProvider

@dataclass
class ResourceManager:
    # ... 现有字段 ...
    embedder_provider_name: str
    _embedder_provider: EmbedderProvider = field(repr=False)      # 新增
    _reranker_provider: RerankerProvider | None = field(default=None, repr=False)  # 新增
    _initialized: bool = field(default=False, init=False, repr=False)
```

**变更点 2：`create()` 方法中创建 reranker 并注入**

```python
@classmethod
def create(cls, settings: Settings) -> "ResourceManager":
    # ... 现有代码 ...

    embedder_provider = create_embedder(embedder_settings)
    embedder_fn = embedder_provider.as_embedder_fn()

    # 新增：创建 reranker
    reranker_provider = create_reranker(settings)
    reranker_fn = reranker_provider.as_reranker_fn() if reranker_provider else None

    # 修改：注入 reranker 到 EpisodicSearchService
    episodic_search = EpisodicSearchService(
        episode_store=episode_store,
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=embedder_fn,
        reranker=reranker_fn,                 # ← 修改：之前没传，现在传入
        rerank_enabled_getter=lambda: memory_config.get_episodic().rerank_enabled,
        metrics=metrics,
        candidate_multiplier=settings.episodic_search_candidate_multiplier,
        max_candidates=settings.episodic_search_max_candidates,
    )

    # ... 构造 ResourceManager 时传入新字段 ...
    resources = cls(
        # ... 现有字段 ...
        _embedder_provider=embedder_provider,
        _reranker_provider=reranker_provider,
    )
    return resources
```

**变更点 3：`initialize()` 方法新增预加载**

```python
async def initialize(self) -> None:
    """Initialize backing stores and schemas."""
    if self._initialized:
        return

    # 模型预加载（启动阶段完成，不让用户首次请求承受延迟）
    await self._embedder_provider.warm_up()
    if self._reranker_provider is not None:
        await self._reranker_provider.warm_up()

    # hash embedder 专用的 jieba 初始化保留
    if self.embedder_provider_name == "hash":
        try:
            import jieba
            jieba.initialize()
        except (ImportError, OSError):
            pass

    await self.sqlite.initialize_schema()
    await self.semantic_feature_store.initialize()
    await self.derivative_index.initialize()
    await self.kuzu.initialize_schema()
    await self.background_tasks.run_startup_recovery()
    self._initialized = True
```

**启动行为变化：**

| 场景 | 启动耗时变化 | 说明 |
|------|-------------|------|
| `embedder_provider=hash` + `reranker_provider=none` | 无变化 | warm_up 都是空操作 |
| `embedder_provider=sentence_transformer` + `reranker_provider=none` | 首次启动多几秒~几十秒（下载+加载模型），后续启动多约 1~3 秒（加载权重） | embedding 模型在启动时加载 |
| `embedder_provider=sentence_transformer` + `reranker_provider=cross_encoder` | 在上面基础上再多 1~3 秒 | 两个模型都在启动时加载 |

**验证方法：**
```bash
uv run --python 3.12 python -m pytest -q tests/unit/test_resources.py tests/unit/test_embedders.py tests/unit/test_rerankers.py
```

---

### T21：pyproject.toml 可选依赖说明更新

**目标：** 确认 `[embeddings]` 依赖组覆盖 embedding + reranker 两个场景。

**当前状态（无需修改）：**
```toml
[project.optional-dependencies]
embeddings = [
    "sentence-transformers>=3.0.0",
]
```

`sentence-transformers` 包同时包含 `SentenceTransformer`（embedding）和 `CrossEncoder`（reranker），
无需额外添加依赖。安装命令：

```bash
pip install memolite[embeddings]
```

**可选：README 补充安装说明**
```
# 仅核心功能（hash embedder，无 reranker）
pip install memolite

# 启用语义 embedding + reranker（需要 ~400MB 额外磁盘）
pip install memolite[embeddings]
```

---

### T22：单元测试

**目标：** 覆盖新增的所有逻辑路径。

**新建：`tests/unit/test_rerankers.py`**

```python
# 测试用例清单：

# 1. test_cross_encoder_provider_name
#    - 验证 provider.name == "cross_encoder"

# 2. test_cross_encoder_warm_up_loads_model (monkeypatch CrossEncoder)
#    - mock sentence_transformers.CrossEncoder
#    - 调用 warm_up() 后 _model 不为 None

# 3. test_cross_encoder_rerank_sorts_by_score (monkeypatch)
#    - mock model.predict 返回 [0.1, 0.9, 0.5]
#    - 验证 rerank 后结果按分数降序排列

# 4. test_cross_encoder_rerank_empty_matches
#    - 空列表输入 → 返回空列表

# 5. test_factory_returns_none_when_disabled
#    - Settings(reranker_provider="none") → create_reranker() returns None

# 6. test_factory_returns_cross_encoder_when_configured
#    - Settings(reranker_provider="cross_encoder") → 返回 CrossEncoderRerankerProvider
#    - 默认 model_name == "BAAI/bge-reranker-base"

# 7. test_factory_respects_custom_model_name
#    - Settings(reranker_provider="cross_encoder", reranker_model="custom/model")
#    - 返回的 provider.model_name == "custom/model"

# 8. test_factory_raises_on_unknown_provider
#    - Settings(reranker_provider="unknown") → ValueError
```

**修改：`tests/unit/test_embedders.py`**

```python
# 新增测试用例：

# 9. test_sentence_transformer_warm_up (monkeypatch)
#    - mock SentenceTransformer
#    - 调用 warm_up() 后 _model 不为 None
#    - 再调用 encode() 不会重复构造模型

# 10. test_hash_embedder_warm_up_is_noop
#     - 调用 warm_up() 不报错，不做任何事

# 11. test_factory_default_model_is_bge_small_zh
#     - Settings(embedder_provider="sentence_transformer") 未指定 model
#     - 验证 provider.model_name == "BAAI/bge-small-zh-v1.5"
```

**修改：`tests/unit/test_resources.py`**

```python
# 新增测试用例：

# 12. test_resource_manager_injects_reranker_when_configured
#     - Settings(reranker_provider="cross_encoder", ...)
#     - 验证 episodic_search._reranker is not None

# 13. test_resource_manager_no_reranker_when_disabled
#     - Settings(reranker_provider="none", ...)
#     - 验证 episodic_search._reranker is None
```

**测试原则：**
- 所有涉及真实模型下载的测试都使用 monkeypatch mock
- 不在 CI 中下载真实模型（避免网络依赖 + 耗时）
- mock 策略与现有 `test_embedders.py` 中的 `FakeModel` 模式一致

**验证方法：**
```bash
uv run --python 3.12 python -m pytest -q tests/unit/test_embedders.py tests/unit/test_rerankers.py tests/unit/test_resources.py tests/unit/test_config.py
```

---

## 执行顺序

```
T15 → T16 → T17 → T18 → T19 → T20 → T21 → T22
 │      │      │      │      │      │
 │      │      └──────┴──────┘      │
 │      │      reranker 模块可并行开发  │
 │      │                           │
 └──────┴───────────────────────────┘
 embedder 改动和 reranker 集成到 resources.py
```

- T15 + T16 可并行
- T17 + T18 + T19 可并行（reranker 模块内部互相依赖但与 embedder 改动无关）
- T20 依赖前面所有任务完成
- T21 独立
- T22 贯穿所有任务，每完成一个 T 就写对应测试

---

## 配置示例

完成后用户的 `.env` 文件：

```env
# Embedding：使用本地语义模型（中文优化）
MEMOLITE_EMBEDDER_PROVIDER=sentence_transformer
MEMOLITE_EMBEDDER_MODEL=BAAI/bge-small-zh-v1.5

# Reranker：使用本地 cross-encoder 精排
MEMOLITE_RERANKER_PROVIDER=cross_encoder
MEMOLITE_RERANKER_MODEL=BAAI/bge-reranker-base
```

首次启动时自动下载模型到 `~/.cache/huggingface/hub/`，后续启动从缓存加载。

---

## 风险与注意事项

| 风险 | 影响 | 缓解 |
|------|------|------|
| bge-small-zh 维度(512) 与旧模型(384) 不兼容 | 历史向量不可用 | 切换后必须执行 `memolite rebuild-vectors`（T7 已实现） |
| 首次启动需下载 ~370MB 模型（embedding 93MB + reranker 278MB） | 离线环境无法使用 | 支持 `MEMOLITE_EMBEDDER_MODEL` 指向本地路径；hash embedder 永远可用作 fallback |
| reranker 增加检索延迟（top-20 精排约 160ms on CPU） | 响应变慢 | `rerank_enabled` 运行时动态开关；`reranker_provider=none` 可彻底关闭 |
| `EpisodeRecord.content` 字段名需确认 | rerank 传错文本 | T18 实现前先 grep 确认字段名 |
