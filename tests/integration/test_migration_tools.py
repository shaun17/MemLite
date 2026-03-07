import json
from pathlib import Path

import pytest
from sqlalchemy import text

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings
from memlite.tools.migration import (
    export_snapshot,
    import_snapshot,
    reconcile_snapshot,
    repair_snapshot,
)


async def _seed_dataset(settings: Settings) -> ResourceManager:
    resources = ResourceManager.create(settings)
    await resources.initialize()
    await resources.orchestrator.create_project(org_id="org-a", project_id="project-a")
    await resources.orchestrator.create_session(
        session_key="session-a",
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
        user_id="user-1",
    )
    await resources.orchestrator.add_episodes(
        session_key="session-a",
        semantic_set_id="session-a",
        episodes=[
            {
                "uid": "ep-1",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 1,
                "content": "Ramen is my favorite food.",
            }
        ],
    )
    feature_id = await resources.semantic_feature_store.add_feature(
        set_id="session-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    await resources.semantic_feature_store.add_citations(feature_id, ["ep-1"])
    return resources


@pytest.mark.anyio
async def test_export_and_import_snapshot_roundtrip(tmp_path: Path):
    source_settings = Settings(
        sqlite_path=tmp_path / "source" / "memlite.sqlite3",
        kuzu_path=tmp_path / "source" / "kuzu",
    )
    resources = await _seed_dataset(source_settings)
    await resources.close()

    snapshot_path = tmp_path / "snapshot.json"
    await export_snapshot(source_settings, snapshot_path)
    exported = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert exported["tables"]["projects"][0]["project_id"] == "project-a"
    assert exported["tables"]["episodes"][0]["uid"] == "ep-1"
    assert exported["tables"]["semantic_features"][0]["feature_name"] == "favorite_food"

    target_settings = Settings(
        sqlite_path=tmp_path / "target" / "memlite.sqlite3",
        kuzu_path=tmp_path / "target" / "kuzu",
    )
    await import_snapshot(target_settings, snapshot_path)

    imported = ResourceManager.create(target_settings)
    await imported.initialize()
    try:
        assert len(await imported.project_store.list_projects()) == 1
        assert len(await imported.episode_store.list_episodes(session_key="session-a")) == 1
        assert len(
            await imported.semantic_feature_store.get_feature_set(set_id="session-a")
        ) == 1
        derivative_nodes = await imported.graph_store.search_matching_nodes(
            node_table="Derivative"
        )
        assert derivative_nodes
    finally:
        await imported.close()


@pytest.mark.anyio
async def test_reconcile_and_repair_tools(tmp_path: Path):
    settings = Settings(
        sqlite_path=tmp_path / "memlite.sqlite3",
        kuzu_path=tmp_path / "kuzu",
    )
    resources = await _seed_dataset(settings)
    engine = resources.sqlite.create_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM semantic_feature_vectors"))
        await conn.execute(text("DELETE FROM derivative_feature_vectors"))
    await resources.kuzu.execute("MATCH (n:Derivative) DETACH DELETE n")
    await resources.kuzu.execute("MATCH (n:Episode) DETACH DELETE n")
    await resources.close()

    report = await reconcile_snapshot(settings)

    assert report["missing_embedding_feature_ids"] == [1]
    assert report["missing_episode_graph_nodes"] == ["ep-1"]

    repaired = await repair_snapshot(settings)

    assert repaired["semantic_vectors_rebuilt"] == 0
    assert repaired["episodes_rebuilt"] == 1
    assert repaired["orphan_records_removed"] == 0

    after = await reconcile_snapshot(settings)
    assert after["missing_embedding_feature_ids"] == [1]
    assert after["missing_derivative_vector_ids"] == []
    assert after["missing_episode_graph_nodes"] == []


@pytest.mark.anyio
async def test_repair_cleans_orphans_and_is_idempotent(tmp_path: Path):
    settings = Settings(
        sqlite_path=tmp_path / "memlite.sqlite3",
        kuzu_path=tmp_path / "kuzu",
    )
    resources = await _seed_dataset(settings)
    engine = resources.sqlite.create_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO derivative_feature_vectors (feature_id, embedding_json)
                VALUES (123456, '[1.0, 0.0, 0.0, 0.0]')
                """
            )
        )
    await resources.graph_store.add_nodes(
        node_table="Episode",
        nodes=[
            {
                "uid": "orphan-episode",
                "session_id": "ghost",
                "content": "ghost",
                "content_type": "text",
                "created_at": "2026-03-06T00:00:00Z",
                "metadata_json": "{}",
            }
        ],
    )
    await resources.graph_store.add_nodes(
        node_table="Derivative",
        nodes=[
            {
                "uid": "orphan-derivative",
                "episode_uid": "orphan-episode",
                "session_id": "ghost",
                "content": "ghost",
                "content_type": "text",
                "sequence_num": 1,
                "metadata_json": "{}",
            }
        ],
    )
    await resources.close()

    first = await repair_snapshot(settings)
    second = await repair_snapshot(settings)

    assert first["orphan_records_removed"] >= 3
    assert second["orphan_records_removed"] == 0

    after = await reconcile_snapshot(settings)
    assert after["orphan_derivative_vector_ids"] == []
    assert after["orphan_episode_graph_nodes"] == []
    assert after["orphan_derivative_nodes"] == []


@pytest.mark.anyio
async def test_migration_roundtrip_preserves_search_consistency(tmp_path: Path):
    source_settings = Settings(
        sqlite_path=tmp_path / "source" / "memlite.sqlite3",
        kuzu_path=tmp_path / "source" / "kuzu",
    )
    resources = await _seed_dataset(source_settings)
    before = await resources.orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
    )
    await resources.close()

    snapshot_path = tmp_path / "snapshot.json"
    await export_snapshot(source_settings, snapshot_path)

    target_settings = Settings(
        sqlite_path=tmp_path / "target" / "memlite.sqlite3",
        kuzu_path=tmp_path / "target" / "kuzu",
    )
    await import_snapshot(target_settings, snapshot_path)

    imported = ResourceManager.create(target_settings)
    await imported.initialize()
    try:
        after = await imported.orchestrator.search_memories(
            query="food ramen",
            session_key="session-a",
            session_id="session-a",
            semantic_set_id="session-a",
        )
    finally:
        await imported.close()

    assert [item.source for item in before.combined] == [
        item.source for item in after.combined
    ]
    assert [item.identifier for item in before.combined] == [
        item.identifier for item in after.combined
    ]
