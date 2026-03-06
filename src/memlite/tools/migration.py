"""Migration, reconciliation and repair tools for MemLite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings

EXPORT_TABLES = (
    "projects",
    "sessions",
    "episodes",
    "semantic_config_set_type",
    "semantic_config_set_id_resources",
    "semantic_config_set_id_set_type",
    "semantic_config_category",
    "semantic_config_category_template",
    "semantic_config_tag",
    "semantic_config_disabled_category",
    "semantic_features",
    "semantic_feature_vectors",
    "semantic_citations",
    "semantic_set_ingested_history",
)


async def export_snapshot(settings: Settings, output: Path) -> Path:
    """Export the current MemLite state into a JSON snapshot."""
    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        engine = resources.sqlite.create_engine()
        snapshot: dict[str, Any] = {"tables": {}}
        async with engine.connect() as conn:
            for table in EXPORT_TABLES:
                rows = (await conn.execute(text(f"SELECT * FROM {table}"))).mappings().all()
                snapshot["tables"][table] = [dict(row) for row in rows]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        return output
    finally:
        await resources.close()


async def import_snapshot(settings: Settings, source: Path) -> None:
    """Import a MemLite JSON snapshot into SQLite and rebuild derived state."""
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    tables: dict[str, list[dict[str, Any]]] = snapshot["tables"]
    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        await _truncate_sqlite_tables(resources, reversed(EXPORT_TABLES))
        async with resources.sqlite.create_engine().begin() as conn:
            for table in EXPORT_TABLES:
                for row in tables.get(table, []):
                    columns = list(row.keys())
                    placeholders = ", ".join(f":{column}" for column in columns)
                    statement = (
                        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) "
                        f"VALUES ({placeholders})"
                    )
                    await conn.execute(text(statement), row)
        await rebuild_semantic_vectors(resources)
        await rebuild_derivative_graph(resources)
    finally:
        await resources.close()


async def rebuild_semantic_vectors(resources: ResourceManager) -> int:
    """Rebuild semantic feature vector table from stored vector payloads."""
    engine = resources.sqlite.create_engine()
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text("SELECT feature_id, embedding_json FROM semantic_feature_vectors")
            )
        ).all()
        await conn.execute(text("DELETE FROM semantic_feature_vectors"))
        for feature_id, embedding_json in rows:
            await conn.execute(
                text(
                    """
                    INSERT INTO semantic_feature_vectors (feature_id, embedding_json)
                    VALUES (:feature_id, :embedding_json)
                    """
                ),
                {"feature_id": feature_id, "embedding_json": embedding_json},
            )
    return len(rows)


async def rebuild_derivative_graph(resources: ResourceManager) -> int:
    """Rebuild Kùzu graph nodes/edges and derivative vector index from episodes."""
    await resources.kuzu.execute("MATCH (n:Derivative) DETACH DELETE n")
    await resources.kuzu.execute("MATCH (n:Episode) DETACH DELETE n")
    engine = resources.sqlite.create_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM derivative_feature_vectors"))
    episodes = await resources.episode_store.find_matching_episodes(include_deleted=False)
    count = 0
    for episode in episodes:
        await resources.derivative_pipeline.create_derivatives(episode)
        count += 1
    return count


async def reconcile_snapshot(settings: Settings) -> dict[str, Any]:
    """Reconcile SQLite, sqlite-vec and Kùzu state."""
    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        sqlite_vec = await _reconcile_sqlite_vec(resources)
        kuzu = await _reconcile_kuzu(resources)
        return {**sqlite_vec, **kuzu}
    finally:
        await resources.close()


async def repair_snapshot(settings: Settings) -> dict[str, int]:
    """Repair missing derivative vectors and graph state from SQLite truth."""
    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        semantic_count = await rebuild_semantic_vectors(resources)
        derivative_count = await rebuild_derivative_graph(resources)
        orphan_deleted = await _cleanup_soft_delete_residue(resources)
        return {
            "semantic_vectors_rebuilt": semantic_count,
            "episodes_rebuilt": derivative_count,
            "soft_delete_residue_removed": orphan_deleted,
        }
    finally:
        await resources.close()


async def _truncate_sqlite_tables(
    resources: ResourceManager,
    tables: Any,
) -> None:
    async with resources.sqlite.create_engine().begin() as conn:
        for table in tables:
            await conn.execute(text(f"DELETE FROM {table}"))
        await conn.execute(text("DELETE FROM derivative_feature_vectors"))


async def _reconcile_sqlite_vec(resources: ResourceManager) -> dict[str, Any]:
    engine = resources.sqlite.create_engine()
    async with engine.connect() as conn:
        feature_ids = {
            int(row[0])
            for row in (
                await conn.execute(
                    text("SELECT id FROM semantic_features WHERE deleted = 0 ORDER BY id")
                )
            ).all()
        }
        vector_ids = {
            int(row[0])
            for row in (
                await conn.execute(
                    text("SELECT feature_id FROM semantic_feature_vectors ORDER BY feature_id")
                )
            ).all()
        }
        derivative_vector_ids = {
            int(row[0])
            for row in (
                await conn.execute(
                    text(
                        "SELECT feature_id FROM derivative_feature_vectors ORDER BY feature_id"
                    )
                )
            ).all()
        }
    derivative_nodes = await resources.graph_store.search_matching_nodes(node_table="Derivative")
    derivative_expected = {
        _vector_item_id(str(node.properties["uid"])) for node in derivative_nodes
    }
    return {
        "missing_embedding_feature_ids": sorted(feature_ids - vector_ids),
        "orphan_semantic_vector_ids": sorted(vector_ids - feature_ids),
        "missing_derivative_vector_ids": sorted(derivative_expected - derivative_vector_ids),
        "orphan_derivative_vector_ids": sorted(derivative_vector_ids - derivative_expected),
    }


async def _reconcile_kuzu(resources: ResourceManager) -> dict[str, Any]:
    episodes = await resources.episode_store.find_matching_episodes(include_deleted=False)
    episode_ids = {episode.uid for episode in episodes}
    episode_nodes = await resources.graph_store.search_matching_nodes(node_table="Episode")
    derivative_nodes = await resources.graph_store.search_matching_nodes(node_table="Derivative")
    derivative_episode_ids = {str(node.properties["episode_uid"]) for node in derivative_nodes}
    missing_edges = sorted(derivative_episode_ids - {str(node.properties["uid"]) for node in episode_nodes})
    missing_episode_nodes = sorted(episode_ids - {str(node.properties["uid"]) for node in episode_nodes})
    orphan_episode_nodes = sorted({str(node.properties["uid"]) for node in episode_nodes} - episode_ids)
    orphan_derivative_nodes = sorted(derivative_episode_ids - episode_ids)
    return {
        "missing_graph_edge_episode_ids": missing_edges,
        "missing_episode_graph_nodes": missing_episode_nodes,
        "orphan_episode_graph_nodes": orphan_episode_nodes,
        "orphan_derivative_nodes": orphan_derivative_nodes,
    }


async def _cleanup_soft_delete_residue(resources: ResourceManager) -> int:
    deleted_episodes = await resources.episode_store.find_matching_episodes(include_deleted=True)
    deleted_ids = [episode.uid for episode in deleted_episodes if episode.deleted == 1]
    await resources.semantic_feature_store.delete_history(deleted_ids)
    return len(deleted_ids)


def _vector_item_id(uid: str) -> int:
    from memlite.episodic.derivative_pipeline import vector_item_id

    return vector_item_id(uid)
