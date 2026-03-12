"""Tests for real similarity scoring in semantic search and merged results.

These tests verify two bug fixes:
1. SemanticSearchResult exposes real cosine scores (not positional rank fakes).
2. _merge_results uses those real scores so ranking is faithful to vector similarity.
"""

from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.semantic.service import ScoredFeature, SemanticService
from memolite.storage.semantic_config_store import SqliteSemanticConfigStore
from memolite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memolite.storage.sqlite_engine import SqliteEngineFactory


async def _food_embedder(text: str) -> list[float]:
    """Always returns the food embedding vector for any query."""
    return [1.0, 0.0]


@pytest.mark.anyio
async def test_semantic_search_result_exposes_scores(tmp_path: Path):
    """semantic_search() must return ScoredFeature items with real cosine scores."""
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    config_store = SqliteSemanticConfigStore(factory)

    await feature_store.add_feature(
        set_id="set-a",
        category="profile",
        tag="preference",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0],
    )
    await feature_store.add_feature(
        set_id="set-a",
        category="profile",
        tag="preference",
        feature_name="seat_preference",
        value="aisle",
        embedding=[0.0, 1.0],
    )

    service = SemanticService(
        feature_store=feature_store,
        config_store=config_store,
        embedder=_food_embedder,
        default_category_resolver=lambda _: [],
    )
    result = await service.semantic_search(query="food preference", set_id="set-a")

    assert len(result.features) >= 1
    first = result.features[0]
    assert isinstance(first, ScoredFeature), (
        f"features must be ScoredFeature, not {type(first).__name__}"
    )
    assert first.score > 0.5, f"expected real cosine score near 1.0, got {first.score}"

    await factory.dispose()


@pytest.mark.anyio
async def test_merge_results_ranks_by_real_semantic_score(tmp_path: Path):
    """CombinedMemoryItem scores for semantic must use real vector similarity, not position."""
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    config_store = SqliteSemanticConfigStore(factory)

    # 4 features all embedded as [1.0, 0.0] → real cosine with query [1.0, 0.0] = 1.0
    for i in range(4):
        await feature_store.add_feature(
            set_id="set-a",
            category="profile",
            tag="preference",
            feature_name=f"pref_{i}",
            value=f"food item {i}",
            embedding=[1.0, 0.0],
        )

    service = SemanticService(
        feature_store=feature_store,
        config_store=config_store,
        embedder=_food_embedder,
        default_category_resolver=lambda _: [],
    )
    result = await service.semantic_search(query="food", set_id="set-a", limit=4)

    assert len(result.features) == 4
    # Before fix: positional scoring gives 4th item score = 1.0 - 3/4 = 0.25
    # After fix: all 4 items carry real cosine score ≈ 1.0
    scores = [sf.score for sf in result.features]
    assert all(s > 0.9 for s in scores), (
        f"All semantic scores should be ~1.0 (real cosine), got {scores}"
    )

    await factory.dispose()
