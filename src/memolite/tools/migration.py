"""Migration, reconciliation and repair tools for MemLite."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

from sqlalchemy import text

from memolite.common.config import Settings

if TYPE_CHECKING:
    from memolite.app.resources import ResourceManager

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
    "derivative_feature_vectors",
    "semantic_citations",
    "semantic_set_ingested_history",
)


async def export_snapshot(settings: Settings, output: Path) -> Path:
    """Export the current MemLite state into a JSON snapshot."""
    from memolite.app.resources import ResourceManager

    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        engine = resources.sqlite.create_engine()
        snapshot: dict[str, Any] = {"tables": {}}
        async with engine.connect() as conn:
            for table in EXPORT_TABLES:
                rows = (await conn.execute(text(f"SELECT * FROM {table}"))).mappings().all()
                snapshot["tables"][table] = [_json_safe_row(dict(row)) for row in rows]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        return output
    finally:
        await resources.close()


async def import_snapshot(settings: Settings, source: Path) -> None:
    """Import a MemLite JSON snapshot into SQLite and rebuild derived state."""
    from memolite.app.resources import ResourceManager

    snapshot = json.loads(source.read_text(encoding="utf-8"))
    tables: dict[str, list[dict[str, Any]]] = snapshot["tables"]
    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        await _truncate_sqlite_tables(resources, reversed(EXPORT_TABLES))
        async with resources.sqlite.create_engine().begin() as conn:
            for table in EXPORT_TABLES:
                for row in tables.get(table, []):
                    restored_row = _restore_snapshot_row(row)
                    columns = list(restored_row.keys())
                    placeholders = ", ".join(f":{column}" for column in columns)
                    statement = (
                        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) "
                        f"VALUES ({placeholders})"
                    )
                    await conn.execute(text(statement), restored_row)
        await rebuild_semantic_vectors(resources)
        await rebuild_derivative_graph(resources)
    finally:
        await resources.close()


async def rebuild_semantic_vectors(resources: ResourceManager) -> int:
    """Rebuild semantic vector table from stored vector payloads.

    Semantic vectors currently only live in SQLite vector storage, so this
    routine can preserve and normalize existing rows but cannot recreate
    missing embeddings from first principles.
    """
    engine = resources.sqlite.create_engine()
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text("SELECT feature_id, embedding FROM semantic_feature_vectors")
            )
        ).all()
        await conn.execute(text("DELETE FROM semantic_feature_vectors"))
        for feature_id, embedding in rows:
            await conn.execute(
                text(
                    """
                    INSERT INTO semantic_feature_vectors (feature_id, embedding)
                    VALUES (:feature_id, :embedding)
                    """
                ),
                {"feature_id": feature_id, "embedding": embedding},
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
    from memolite.app.resources import ResourceManager

    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        return await reconcile_runtime(resources)
    finally:
        await resources.close()


async def reconcile_runtime(resources: ResourceManager) -> dict[str, Any]:
    """Reconcile live runtime resources without creating a nested container."""
    sqlite_vec = await _reconcile_sqlite_vec(resources)
    kuzu = await _reconcile_kuzu(resources)
    return {**sqlite_vec, **kuzu}


async def repair_snapshot(settings: Settings) -> dict[str, int]:
    """Repair missing derivative vectors and graph state from SQLite truth."""
    from memolite.app.resources import ResourceManager

    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        orphan_deleted = await cleanup_orphan_data(resources)
        semantic_count = await rebuild_semantic_vectors(resources)
        derivative_count = await rebuild_derivative_graph(resources)
        residue_deleted = await _cleanup_soft_delete_residue(resources)
        return {
            "semantic_vectors_rebuilt": semantic_count,
            "episodes_rebuilt": derivative_count,
            "orphan_records_removed": orphan_deleted,
            "soft_delete_residue_removed": residue_deleted,
        }
    finally:
        await resources.close()


async def rebuild_vectors_snapshot(
    settings: Settings,
    *,
    target: str = "all",
) -> dict[str, int]:
    """Rebuild semantic and/or derivative vectors from persisted source data."""
    from memolite.app.resources import ResourceManager

    if target not in {"semantic", "derivative", "all"}:
        raise ValueError(f"unsupported rebuild target: {target}")

    resources = ResourceManager.create(settings)
    await resources.initialize()
    try:
        semantic_count = 0
        derivative_count = 0
        if target in {"semantic", "all"}:
            semantic_count = await rebuild_semantic_vectors(resources)
        if target in {"derivative", "all"}:
            derivative_count = await rebuild_derivative_graph(resources)
        return {
            "semantic_vectors_rebuilt": semantic_count,
            "episodes_rebuilt": derivative_count,
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


async def cleanup_orphan_data(resources: ResourceManager) -> int:
    """Clean orphan vectors and graph nodes that are not backed by SQLite truth."""
    report = await _reconcile_sqlite_vec(resources)
    graph_report = await _reconcile_kuzu(resources)
    deleted = 0

    orphan_semantic_vector_ids = report["orphan_semantic_vector_ids"]
    if orphan_semantic_vector_ids:
        await resources.semantic_feature_store.vector_index.delete_many(orphan_semantic_vector_ids)
        deleted += len(orphan_semantic_vector_ids)

    orphan_derivative_vector_ids = report["orphan_derivative_vector_ids"]
    if orphan_derivative_vector_ids:
        await resources.derivative_index.delete_many(orphan_derivative_vector_ids)
        deleted += len(orphan_derivative_vector_ids)

    orphan_episode_graph_nodes = graph_report["orphan_episode_graph_nodes"]
    if orphan_episode_graph_nodes:
        await resources.graph_store.delete_nodes(
            node_table="Episode",
            uids=orphan_episode_graph_nodes,
        )
        deleted += len(orphan_episode_graph_nodes)

    orphan_derivative_nodes = graph_report["orphan_derivative_nodes"]
    if orphan_derivative_nodes:
        await resources.graph_store.delete_nodes(
            node_table="Derivative",
            uids=orphan_derivative_nodes,
        )
        deleted += len(orphan_derivative_nodes)

    return deleted


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (bytes, bytearray, memoryview)):
            converted[key] = {
                "__memolite_encoding__": "base64",
                "data": base64.b64encode(bytes(value)).decode("ascii"),
            }
        else:
            converted[key] = value
    return converted


def _restore_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    restored: dict[str, Any] = {}
    for key, value in row.items():
        if (
            isinstance(value, dict)
            and value.get("__memolite_encoding__") == "base64"
            and "data" in value
        ):
            restored[key] = base64.b64decode(value["data"])
        else:
            restored[key] = value
    return restored


def _vector_item_id(uid: str) -> int:
    from memolite.episodic.derivative_pipeline import vector_item_id

    return vector_item_id(uid)
