"""Semantic service orchestration for MemLite."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from memlite.storage.semantic_config_store import (
    CategoryRecord,
    SetConfigRecord,
    SqliteSemanticConfigStore,
)
from memlite.storage.semantic_feature_store import (
    SemanticFeatureRecord,
    SqliteSemanticFeatureStore,
)
from memlite.storage.sqlite_vec import VectorSearchResult

EmbedderFn = Callable[[str], Awaitable[list[float]]]
DefaultCategoryResolver = Callable[[str], Sequence[CategoryRecord]]
HistoryProcessor = Callable[[str, list[str]], Awaitable[int]]


@dataclass(slots=True)
class SemanticSearchResult:
    """Search result containing matched semantic features."""

    features: list[SemanticFeatureRecord]


class SemanticService:
    """Coordinate semantic storage, configuration and retrieval."""

    def __init__(
        self,
        *,
        feature_store: SqliteSemanticFeatureStore,
        config_store: SqliteSemanticConfigStore,
        embedder: EmbedderFn,
        default_category_resolver: DefaultCategoryResolver,
    ) -> None:
        self._feature_store = feature_store
        self._config_store = config_store
        self._embedder = embedder
        self._default_category_resolver = default_category_resolver

    async def get_default_categories(self, set_id: str) -> list[CategoryRecord]:
        """Return effective categories after config merge and disable rules."""
        configured_categories = await self._config_store.list_categories_for_set(set_id)
        injected_categories = list(self._default_category_resolver(set_id))
        disabled_names = set(await self._config_store.get_disabled_categories(set_id))

        merged: dict[str, CategoryRecord] = {}
        for category in injected_categories:
            if category.name in disabled_names:
                continue
            merged.setdefault(category.name, category)
        for category in configured_categories:
            if category.name in disabled_names:
                continue
            merged[category.name] = category
        return list(merged.values())

    async def get_effective_set_config(self, set_id: str) -> SetConfigRecord | None:
        """Return set-level configuration if present."""
        return await self._config_store.get_setid_config(set_id)

    async def generate_feature_embedding(self, text: str) -> list[float]:
        """Generate an embedding for semantic retrieval."""
        return await self._embedder(text)

    async def semantic_search(
        self,
        *,
        query: str,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        limit: int = 5,
        min_score: float = 0.0001,
    ) -> SemanticSearchResult:
        """Search semantic features using vector similarity and filters."""
        embedding = await self.generate_feature_embedding(query)
        vector_hits = await self._feature_store.vector_index.search_top_k(
            embedding, limit=max(limit * 3, limit)
        )
        eligible_hits = _select_positive_hits(vector_hits, min_score=min_score)
        hit_ids = [hit.item_id for hit in eligible_hits]
        if not hit_ids:
            return SemanticSearchResult(features=[])

        allowed_categories = await self._resolve_allowed_categories(set_id, category)
        features = await self._feature_store.query_features(
            set_id=set_id,
            category=category,
            tag=tag,
            include_deleted=False,
        )
        feature_map = {
            feature.id: feature
            for feature in features
            if allowed_categories is None or feature.category in allowed_categories
        }
        ordered = [feature_map[item_id] for item_id in hit_ids if item_id in feature_map]
        return SemanticSearchResult(features=ordered[:limit])

    async def semantic_list(
        self,
        *,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        page_size: int | None = None,
        page_num: int | None = None,
    ) -> list[SemanticFeatureRecord]:
        """List semantic features with optional filters and pagination."""
        allowed_categories = await self._resolve_allowed_categories(set_id, category)
        features = await self._feature_store.get_feature_set(
            set_id=set_id,
            category=category,
            tag=tag,
            page_size=page_size,
            page_num=page_num,
        )
        if allowed_categories is None:
            return features
        return [feature for feature in features if feature.category in allowed_categories]

    async def semantic_delete(
        self,
        *,
        feature_ids: list[int] | None = None,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> None:
        """Delete semantic features by ids or by filter set."""
        if feature_ids:
            await self._feature_store.delete_features(feature_ids)
            return

        allowed_categories = await self._resolve_allowed_categories(set_id, category)
        if allowed_categories is None:
            await self._feature_store.delete_feature_set(
                set_id=set_id,
                category=category,
                tag=tag,
            )
            return

        features = await self._feature_store.query_features(
            set_id=set_id,
            category=category,
            tag=tag,
            include_deleted=False,
        )
        deletable_ids = [
            feature.id for feature in features if feature.category in allowed_categories
        ]
        await self._feature_store.delete_features(deletable_ids)

    async def _resolve_allowed_categories(
        self,
        set_id: str | None,
        category: str | None,
    ) -> set[str] | None:
        if category is not None or set_id is None:
            return None if category is None else {category}
        categories = await self.get_default_categories(set_id)
        if not categories:
            return None
        return {category_record.name for category_record in categories}


class SemanticIngestionWorker:
    """Process pending semantic history items."""

    def __init__(
        self,
        *,
        feature_store: SqliteSemanticFeatureStore,
        processor: HistoryProcessor,
    ) -> None:
        self._feature_store = feature_store
        self._processor = processor

    async def process_pending(self, set_id: str) -> int:
        """Process non-ingested history items for a single set."""
        history_ids = await self._feature_store.get_history_messages(
            set_ids=[set_id], is_ingested=False
        )
        if not history_ids:
            return 0
        processed = await self._processor(set_id, history_ids)
        if processed > 0:
            await self._feature_store.mark_messages_ingested(
                set_id=set_id,
                history_ids=history_ids,
            )
        return processed


def _select_positive_hits(
    hits: list[VectorSearchResult], *, min_score: float
) -> list[VectorSearchResult]:
    return [hit for hit in hits if hit.score >= min_score]
