"""Kùzu-backed graph store for episodic memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from memlite.storage.kuzu_engine import KuzuEngineFactory

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
            assignments = _render_set_assignments("n", node)
            query = f"""
            MERGE (n:{node_table} {{uid: {_quote(uid)}}})
            {f"SET {assignments}" if assignments else ""}
            """
            await self._engine.execute(query)

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
            WHERE src.uid = {_quote(edge.from_uid)} AND dst.uid = {_quote(edge.to_uid)}
            MERGE (src)-[r:{relation_table}]->(dst)
            SET r.relation_type = {_quote(edge.relation_type)}
            """
            await self._engine.execute(query)

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
        if match_filters:
            for key, value in match_filters.items():
                if key not in properties:
                    continue
                where_clauses.append(f"n.{key} = {_quote(value)}")
        if match_any_uids:
            where_clauses.append(
                "n.uid IN [" + ", ".join(_quote(uid) for uid in match_any_uids) + "]"
            )

        query = "MATCH (n:{table})".format(table=node_table)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " RETURN " + ", ".join(
            f"n.{property_name}" for property_name in properties
        )
        rows = await self._engine.query(query)
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
        WHERE src.uid = {_quote(source_uid)}
        RETURN {", ".join(f"dst.{property_name}" for property_name in properties)}
        """
        rows = await self._engine.query(query)
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
        predicate = "n.uid IN [" + ", ".join(_quote(uid) for uid in uids) + "]"
        await self._engine.execute(
            f"MATCH (n:{node_table}) WHERE {predicate} DETACH DELETE n"
        )


def _render_properties(properties: dict[str, object | None]) -> str:
    return ", ".join(
        f"{key}: {_quote(value)}"
        for key, value in properties.items()
        if value is not None
    )


def _render_set_assignments(alias: str, properties: dict[str, object | None]) -> str:
    assignments = [
        f"{alias}.{key} = {_quote(value)}"
        for key, value in properties.items()
        if key != "uid" and value is not None
    ]
    return ", ".join(assignments)


def _quote(value: object | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))
