from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.graph_store import GraphEdgeRecord, KuzuGraphStore
from memlite.storage.kuzu_engine import KuzuEngineFactory


@pytest.mark.anyio
async def test_graph_store_add_get_search_and_delete_nodes(tmp_path: Path):
    engine = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "graph.kuzu"))
    await engine.initialize_schema()
    store = KuzuGraphStore(engine)

    await store.add_nodes(
        node_table="Episode",
        nodes=[
            {
                "uid": "ep-1",
                "session_id": "s1",
                "content": "hello",
                "content_type": "text",
                "created_at": "2026-03-06T00:00:00Z",
                "metadata_json": '{"kind":"episode"}',
            },
            {
                "uid": "ep-2",
                "session_id": "s1",
                "content": "world",
                "content_type": "text",
                "created_at": "2026-03-06T00:01:00Z",
                "metadata_json": '{"kind":"episode"}',
            },
        ],
    )

    fetched = await store.get_nodes(node_table="Episode", uids=["ep-1", "ep-2"])
    filtered = await store.search_matching_nodes(
        node_table="Episode",
        match_filters={"session_id": "s1", "content_type": "text"},
    )
    await store.delete_nodes(node_table="Episode", uids=["ep-2"])
    remaining = await store.get_nodes(node_table="Episode", uids=["ep-1", "ep-2"])

    assert {node.properties["uid"] for node in fetched} == {"ep-1", "ep-2"}
    assert {node.properties["uid"] for node in filtered} == {"ep-1", "ep-2"}
    assert [node.properties["uid"] for node in remaining] == ["ep-1"]

    await engine.close()


@pytest.mark.anyio
async def test_graph_store_related_and_directional_queries(tmp_path: Path):
    engine = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "graph.kuzu"))
    await engine.initialize_schema()
    store = KuzuGraphStore(engine)

    await store.add_nodes(
        node_table="Episode",
        nodes=[
            {
                "uid": "ep-1",
                "session_id": "s1",
                "content": "episode one",
                "content_type": "text",
                "created_at": "2026-03-06T00:00:00Z",
                "metadata_json": "{}",
            }
        ],
    )
    await store.add_nodes(
        node_table="Derivative",
        nodes=[
            {
                "uid": "der-1",
                "episode_uid": "ep-1",
                "session_id": "s1",
                "content": "chunk one",
                "content_type": "text",
                "sequence_num": 1,
                "metadata_json": "{}",
            }
        ],
    )
    await store.add_edges(
        relation_table="DERIVED_FROM",
        from_table="Derivative",
        to_table="Episode",
        edges=[
            GraphEdgeRecord(
                from_table="Derivative",
                from_uid="der-1",
                to_table="Episode",
                to_uid="ep-1",
                relation_table="DERIVED_FROM",
                relation_type="derived",
            )
        ],
    )

    outgoing = await store.search_related_nodes(
        source_table="Derivative",
        source_uid="der-1",
        relation_table="DERIVED_FROM",
        target_table="Episode",
    )
    incoming = await store.search_directional_nodes(
        source_table="Episode",
        source_uid="ep-1",
        relation_table="DERIVED_FROM",
        target_table="Derivative",
        direction="in",
    )

    assert [node.properties["uid"] for node in outgoing] == ["ep-1"]
    assert [node.properties["uid"] for node in incoming] == ["der-1"]

    await engine.close()
