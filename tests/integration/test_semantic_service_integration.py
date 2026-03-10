from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.semantic.service import SemanticIngestionWorker, SemanticService
from memlite.storage.semantic_config_store import CategoryRecord, SqliteSemanticConfigStore
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


async def fake_embedder(text: str) -> list[float]:
    return [1.0, 0.0] if "food" in text else [0.0, 1.0]


@pytest.mark.anyio
async def test_semantic_service_respects_config_and_vector_search(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    config_store = SqliteSemanticConfigStore(factory)
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    await config_store.set_setid_config(
        set_id="set-a",
        embedder_name="fake-embedder",
        language_model_name="fake-llm",
    )
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
        category="hidden",
        tag="food",
        feature_name="internal_flag",
        value="skip",
        embedding=[1.0, 0.0],
    )
    await config_store.create_category(
        set_id="set-a",
        name="profile",
        prompt="profile prompt",
    )
    await config_store.add_disabled_category_to_setid(
        set_id="set-a",
        category_name="hidden",
    )

    service = SemanticService(
        feature_store=feature_store,
        config_store=config_store,
        embedder=fake_embedder,
        default_category_resolver=lambda _set_id: [
            CategoryRecord(
                id=200,
                set_id=None,
                set_type_id=None,
                name="hidden",
                prompt="hidden prompt",
                description=None,
            )
        ],
    )

    config = await service.get_effective_set_config("set-a")
    results = await service.semantic_search(query="food", set_id="set-a")

    assert config is not None
    assert config.embedder_name == "fake-embedder"
    assert [feature.feature_name for feature in results.features] == ["favorite_food"]

    await factory.dispose()


@pytest.mark.anyio
async def test_add_history_ingest_and_search_flow(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    config_store = SqliteSemanticConfigStore(factory)
    feature_store = SqliteSemanticFeatureStore(factory)
    await feature_store.initialize()
    await config_store.create_category(
        set_id="set-a",
        name="profile",
        prompt="profile prompt",
    )
    await feature_store.add_history_to_set("set-a", "episode-food-1")

    async def processor(set_id: str, history_ids: list[str]) -> int:
        for history_id in history_ids:
            feature_id = await feature_store.add_feature(
                set_id=set_id,
                category="profile",
                tag="food",
                feature_name=f"feature_{history_id}",
                value="ramen",
                embedding=[1.0, 0.0],
            )
            await feature_store.add_citations(feature_id, [history_id])
        return len(history_ids)

    worker = SemanticIngestionWorker(feature_store=feature_store, processor=processor)
    service = SemanticService(
        feature_store=feature_store,
        config_store=config_store,
        embedder=fake_embedder,
        default_category_resolver=lambda _set_id: [],
    )

    processed = await worker.process_pending("set-a")
    pending_count = await feature_store.get_history_messages_count(
        set_ids=["set-a"], is_ingested=False
    )
    results = await service.semantic_search(query="food", set_id="set-a")
    citations = await feature_store.get_citations(results.features[0].id)

    assert processed == 1
    assert pending_count == 0
    assert [feature.feature_name for feature in results.features] == [
        "feature_episode-food-1"
    ]
    assert citations == ["episode-food-1"]

    await factory.dispose()
