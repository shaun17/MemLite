from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.semantic.service import SemanticService, _candidate_limit
from memlite.storage.semantic_config_store import SqliteSemanticConfigStore
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


async def fake_embedder(text: str) -> list[float]:
    return [1.0, 0.0] if "food" in text else [0.0, 1.0]


@pytest.mark.anyio
async def test_structured_filters_keep_semantic_search_behavior_stable(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    config_store = SqliteSemanticConfigStore(factory)
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    await feature_store.add_feature(
        set_id="set-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0],
    )
    await feature_store.add_feature(
        set_id="set-a",
        category="profile",
        tag="travel",
        feature_name="seat_preference",
        value="aisle",
        embedding=[0.0, 1.0],
    )
    await config_store.create_category(
        set_id="set-a",
        name="profile",
        prompt="profile prompt",
    )
    service = SemanticService(
        feature_store=feature_store,
        config_store=config_store,
        embedder=fake_embedder,
        default_category_resolver=lambda _set_id: [],
    )

    food_results = await service.semantic_search(
        query="food",
        set_id="set-a",
        category="profile",
        tag="food",
    )
    travel_results = await service.semantic_search(
        query="travel",
        set_id="set-a",
        category="profile",
        tag="travel",
    )

    assert [feature.feature_name for feature in food_results.features] == [
        "favorite_food"
    ]
    assert [feature.feature_name for feature in travel_results.features] == [
        "seat_preference"
    ]

    await factory.dispose()


def test_semantic_candidate_limit_respects_max_candidates():
    assert _candidate_limit(limit=5, multiplier=3, max_candidates=10) == 10
    assert _candidate_limit(limit=2, multiplier=3, max_candidates=10) == 6
