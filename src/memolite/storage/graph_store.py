"""Kùzu-backed graph store for episodic memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from memolite.storage.kuzu_engine import KuzuEngineFactory

NodeTable = Literal["Episode", "Derivative"]
Direction = Literal["out", "in"]

NODE_PROPERTIES: dict[NodeTable, tuple[str, ...]] = {
    "Episode": (
        "uid",
        "session_id",
        "content",
        "content_type",
        "created_at",
        "metadata_json",
    ),
    "Derivative": (
        "uid",
        "episode_uid",
        "session_id",
        "content",
        "content_type",
        "sequence_num",
        "metadata_json",
    ),
}


@dataclass(slots=True)
class GraphNodeRecord:
    """Stored graph node."""

    node_table: NodeTable
    properties: dict[str, object | None]


@dataclass(slots=True)
class GraphEdgeRecord:
    """Stored graph edge."""

    from_table: NodeTable
    from_uid: str
    to_table: NodeTable
    to_uid: str
    relation_table: str
    relation_type: str


class KuzuGraphStore:
    """Graph operations over the MemLite Kùzu schema."""

    def __init__(self, engine: KuzuEngineFactory) -> None:
        self._engine = engine

    async def add_nodes(
        self,
        *,
        node_table: NodeTable,
        nodes: list[dict[str, object | None]],
    ) -> None:
        for node in nodes:
            uid = node.get("uid")
            if uid is None:
                continue
            assignments, parameters = _render_set_assignments("n", node)
            parameters["uid"] = uid
            query = f"""
            MERGE (n:{node_table} {{uid: $uid}})
            {f"SET {assignments}" if assignments else ""}
            """
            await self._engine.execute(query, parameters)

    async def add_edges(
        self,
        *,
        relation_table: str,
        from_table: NodeTable,
        to_table: NodeTable,
        edges: list[GraphEdgeRecord],
    ) -> None:
        for edge in edges:
            query = f"""
            MATCH (src:{from_table}), (dst:{to_table})
            WHERE src.uid = $from_uid AND dst.uid = $to_uid
            MERGE (src)-[r:{relation_table}]->(dst)
            SET r.relation_type = $relation_type
            """
            await self._engine.execute(
                query,
                {
                    "from_uid": edge.from_uid,
                    "to_uid": edge.to_uid,
                    "relation_type": edge.relation_type,
                },
            )

    async def get_nodes(
        self,
        *,
        node_table: NodeTable,
        uids: list[str] | None = None,
    ) -> list[GraphNodeRecord]:
        return await self.search_matching_nodes(
            node_table=node_table,
            match_filters={"uid": uids[0]} if uids and len(uids) == 1 else None,
            match_any_uids=uids if uids and len(uids) > 1 else None,
        )

    async def search_matching_nodes(
        self,
        *,
        node_table: NodeTable,
        match_filters: dict[str, object | None] | None = None,
        match_any_uids: list[str] | None = None,
    ) -> list[GraphNodeRecord]:
        properties = NODE_PROPERTIES[node_table]
        where_clauses: list[str] = []
        parameters: dict[str, object | None] = {}
        if match_filters:
            for key, value in match_filters.items():
                if key not in properties:
                    continue
                parameter_name = f"filter_{key}"
                where_clauses.append(f"n.{key} = ${parameter_name}")
                parameters[parameter_name] = value
        if match_any_uids:
            where_clauses.append("n.uid IN $match_any_uids")
            parameters["match_any_uids"] = match_any_uids

        query = "MATCH (n:{table})".format(table=node_table)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " RETURN " + ", ".join(
            f"n.{property_name}" for property_name in properties
        )
        rows = await self._engine.query(query, parameters)
        return [
            GraphNodeRecord(
                node_table=node_table,
                properties=dict(zip(properties, row, strict=True)),
            )
            for row in rows
        ]

    async def search_related_nodes(
        self,
        *,
        source_table: NodeTable,
        source_uid: str,
        relation_table: str,
        target_table: NodeTable,
    ) -> list[GraphNodeRecord]:
        return await self.search_directional_nodes(
            source_table=source_table,
            source_uid=source_uid,
            relation_table=relation_table,
            target_table=target_table,
            direction="out",
        )

    async def search_related_nodes_batch(
        self,
        *,
        source_table: NodeTable,
        source_uids: list[str],
        relation_table: str,
        target_table: NodeTable,
    ) -> dict[str, list[GraphNodeRecord]]:
        if not source_uids:
            return {}
        properties = NODE_PROPERTIES[target_table]
        query = f"""
        MATCH (src:{source_table})-[:{relation_table}]->(dst:{target_table})
        WHERE src.uid IN $source_uids
        RETURN src.uid, {", ".join(f"dst.{property_name}" for property_name in properties)}
        """
        rows = await self._engine.query(query, {"source_uids": source_uids})
        grouped: dict[str, list[GraphNodeRecord]] = {uid: [] for uid in source_uids}
        for row in rows:
            source_uid = str(row[0])
            grouped.setdefault(source_uid, []).append(
                GraphNodeRecord(
                    node_table=target_table,
                    properties=dict(zip(properties, row[1:], strict=True)),
                )
            )
        return grouped

    async def search_directional_nodes(
        self,
        *,
        source_table: NodeTable,
        source_uid: str,
        relation_table: str,
        target_table: NodeTable,
        direction: Direction,
    ) -> list[GraphNodeRecord]:
        properties = NODE_PROPERTIES[target_table]
        if direction == "out":
            pattern = (
                f"(src:{source_table})-[:{relation_table}]->(dst:{target_table})"
            )
        else:
            pattern = (
                f"(src:{source_table})<-[:{relation_table}]-(dst:{target_table})"
            )

        query = f"""
        MATCH {pattern}
        WHERE src.uid = $source_uid
        RETURN {", ".join(f"dst.{property_name}" for property_name in properties)}
        """
        rows = await self._engine.query(query, {"source_uid": source_uid})
        return [
            GraphNodeRecord(
                node_table=target_table,
                properties=dict(zip(properties, row, strict=True)),
            )
            for row in rows
        ]

    async def delete_nodes(
        self,
        *,
        node_table: NodeTable,
        uids: list[str],
    ) -> None:
        if not uids:
            return
        await self._engine.execute(
            f"MATCH (n:{node_table}) WHERE n.uid IN $uids DETACH DELETE n",
            {"uids": uids},
        )


def _render_set_assignments(
    alias: str,
    properties: dict[str, object | None],
) -> tuple[str, dict[str, object | None]]:
    assignments: list[str] = []
    parameters: dict[str, object | None] = {}
    for key, value in properties.items():
        if key == "uid" or value is None:
            continue
        assignments.append(f"{alias}.{key} = ${key}")
        parameters[key] = value
    return ", ".join(assignments), parameters
