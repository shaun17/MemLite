from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_semantic_feature_store_add_get_update(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSemanticFeatureStore(factory)
    await store.initialize()

    feature_id = await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        metadata_json='{"source":"test"}',
        embedding=[1.0, 0.0],
    )
    feature = await store.get_feature(feature_id)
    await store.update_feature(
        feature_id,
        value="sushi",
        embedding=[0.9, 0.1],
    )
    updated = await store.get_feature(feature_id)
    results = await store.vector_index.search_top_k([1.0, 0.0], limit=1)

    assert feature is not None
    assert feature.value == "ramen"
    assert updated is not None
    assert updated.value == "sushi"
    assert results[0].item_id == feature_id

    await factory.dispose()


@pytest.mark.anyio
async def test_semantic_feature_store_query_delete_and_history(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSemanticFeatureStore(factory)
    await store.initialize()

    first_id = await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
    )
    second_id = await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="travel",
        feature_name="seat_preference",
        value="aisle",
    )

    queried = await store.get_feature_set(set_id="set-a", page_size=1, page_num=0)
    filtered = await store.query_features(tag="travel")
    await store.add_citations(second_id, ["episode-1", "episode-2"])
    citations = await store.get_citations(second_id)
    await store.add_history_to_set("set-a", "episode-1")
    await store.add_history_to_set("set-a", "episode-2")
    history = await store.get_history_messages(set_ids=["set-a"], is_ingested=False)
    history_count = await store.get_history_messages_count(
        set_ids=["set-a"], is_ingested=False
    )
    await store.mark_messages_ingested(set_id="set-a", history_ids=["episode-1"])
    pending_set_ids = await store.get_history_set_ids(min_uningested_messages=1)
    set_ids = await store.get_set_ids_starts_with("set-")
    await store.delete_feature_set(tag="travel")
    deleted_feature = await store.get_feature(second_id)
    await store.delete_features([first_id])
    first_feature = await store.get_feature(first_id)
    await store.delete_history(["episode-2"])
    remaining_history = await store.get_history_messages(set_ids=["set-a"])
    remaining_citations = await store.get_citations(second_id)

    assert [feature.id for feature in queried] == [first_id]
    assert [feature.id for feature in filtered] == [second_id]
    assert citations == ["episode-1", "episode-2"]
    assert history == ["episode-1", "episode-2"]
    assert history_count == 2
    assert pending_set_ids == ["set-a"]
    assert set_ids == ["set-a"]
    assert deleted_feature is not None and deleted_feature.deleted == 1
    assert first_feature is not None and first_feature.deleted == 1
    assert remaining_history == ["episode-1"]
    assert remaining_citations == ["episode-1"]

    await factory.dispose()


@pytest.mark.anyio
async def test_semantic_feature_store_add_is_idempotent_for_same_payload(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSemanticFeatureStore(factory)
    await store.initialize()

    first_id = await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        metadata_json='{"source":"same"}',
        embedding=[1.0, 0.0],
    )
    second_id = await store.add_feature(
        set_id="set-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        metadata_json='{"source":"same"}',
        embedding=[1.0, 0.0],
    )
    features = await store.query_features(set_id="set-a")

    assert first_id == second_id
    assert [feature.id for feature in features] == [first_id]

    await factory.dispose()
