from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_semantic_feature_store_reloads_features_and_vectors(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()
    store = SqliteSemanticFeatureStore(factory)
    await store.initialize()
    feature_id = await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="travel",
        feature_name="seat_preference",
        value="aisle",
        embedding=[0.2, 0.8],
    )
    await factory.dispose()

    reloaded_factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    reloaded_store = SqliteSemanticFeatureStore(reloaded_factory)
    await reloaded_store.initialize()
    feature = await reloaded_store.get_feature(feature_id)
    results = await reloaded_store.vector_index.search_top_k([0.2, 0.8], limit=1)

    assert feature is not None
    assert feature.feature_name == "seat_preference"
    assert results[0].item_id == feature_id

    await reloaded_factory.dispose()


@pytest.mark.anyio
async def test_semantic_feature_store_history_and_pagination_reload(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()
    store = SqliteSemanticFeatureStore(factory)
    await store.initialize()
    await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
    )
    await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="travel",
        feature_name="seat_preference",
        value="aisle",
    )
    await store.add_history_to_set("set-a", "episode-1")
    await store.add_history_to_set("set-a", "episode-2")
    await store.mark_messages_ingested(set_id="set-a", history_ids=["episode-1"])
    await factory.dispose()

    reloaded_factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    reloaded_store = SqliteSemanticFeatureStore(reloaded_factory)
    page = await reloaded_store.get_feature_set(set_id="set-a", page_size=1, page_num=1)
    history = await reloaded_store.get_history_messages(set_ids=["set-a"], limit=2)
    pending_set_ids = await reloaded_store.get_history_set_ids(min_uningested_messages=1)

    assert len(page) == 1
    assert page[0].feature_name == "seat_preference"
    assert history == ["episode-1", "episode-2"]
    assert pending_set_ids == ["set-a"]

    await reloaded_factory.dispose()
