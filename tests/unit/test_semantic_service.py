from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.semantic.service import SemanticIngestionWorker, SemanticService
from memolite.storage.semantic_config_store import CategoryRecord, SqliteSemanticConfigStore
from memolite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memolite.storage.sqlite_engine import SqliteEngineFactory


async def fake_embedder(text: str) -> list[float]:
    if "food" in text:
        return [1.0, 0.0]
    return [0.0, 1.0]


@pytest.mark.anyio
async def test_semantic_service_search_list_delete(tmp_path: Path):
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

    local_category_id = await config_store.create_category(
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

    search = await service.semantic_search(query="food preference", set_id="set-a")
    listed = await service.semantic_list(set_id="set-a", page_size=10, page_num=0)
    defaults = await service.get_default_categories("set-a")
    config = await service.get_effective_set_config("set-a")
    await service.semantic_delete(set_id="set-a", tag="travel")
    remaining = await service.semantic_list(set_id="set-a")

    assert [sf.feature.feature_name for sf in search.features] == ["favorite_food"]
    assert len(listed) == 2
    assert [category.name for category in defaults] == ["profile"]
    assert config is None
    assert [feature.feature_name for feature in remaining] == ["favorite_food"]

    await config_store.delete_category(local_category_id)
    await factory.dispose()


@pytest.mark.anyio
async def test_semantic_service_applies_default_and_disabled_categories(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    config_store = SqliteSemanticConfigStore(factory)
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()

    default_category = CategoryRecord(
        id=100,
        set_id=None,
        set_type_id=None,
        name="profile",
        prompt="default profile",
        description=None,
    )
    local_category_id = await config_store.create_category(
        set_id="set-a",
        name="travel",
        prompt="travel prompt",
    )
    await config_store.add_disabled_category_to_setid(
        set_id="set-a",
        category_name="profile",
    )

    service = SemanticService(
        feature_store=feature_store,
        config_store=config_store,
        embedder=fake_embedder,
        default_category_resolver=lambda _set_id: [default_category],
    )

    categories = await service.get_default_categories("set-a")

    assert [category.name for category in categories] == ["travel"]

    await config_store.delete_category(local_category_id)
    await factory.dispose()


@pytest.mark.anyio
async def test_semantic_ingestion_worker_marks_history_ingested(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    await feature_store.add_history_to_set("set-a", "episode-1")
    await feature_store.add_history_to_set("set-a", "episode-2")

    async def processor(set_id: str, history_ids: list[str]) -> int:
        assert set_id == "set-a"
        assert history_ids == ["episode-1", "episode-2"]
        return len(history_ids)

    worker = SemanticIngestionWorker(feature_store=feature_store, processor=processor)
    processed = await worker.process_pending("set-a")
    pending_count = await feature_store.get_history_messages_count(
        set_ids=["set-a"], is_ingested=False
    )

    assert processed == 2
    assert pending_count == 0

    await factory.dispose()


@pytest.mark.anyio
async def test_semantic_ingestion_worker_keeps_history_when_processor_skips(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    await feature_store.add_history_to_set("set-a", "episode-1")

    async def processor(_set_id: str, _history_ids: list[str]) -> int:
        return 0

    worker = SemanticIngestionWorker(feature_store=feature_store, processor=processor)
    processed = await worker.process_pending("set-a")
    pending_history = await feature_store.get_history_messages(
        set_ids=["set-a"], is_ingested=False
    )

    assert processed == 0
    assert pending_history == ["episode-1"]

    await factory.dispose()
