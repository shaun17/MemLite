import json
from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.episodic.derivative_pipeline import DerivativePipeline
from memolite.storage.episode_store import EpisodeRecord
from memolite.storage.graph_store import KuzuGraphStore
from memolite.storage.kuzu_engine import KuzuEngineFactory
from memolite.storage.sqlite_engine import SqliteEngineFactory
from memolite.storage.sqlite_vec import SqliteVecIndex


async def fake_embedder(text: str) -> list[float]:
    return [float(len(text)), 1.0]


def build_episode() -> EpisodeRecord:
    return EpisodeRecord(
        uid="ep-1",
        session_key="session-key",
        session_id="session-1",
        producer_id="user-1",
        producer_role="user",
        produced_for_id=None,
        sequence_num=1,
        content="First sentence. Second sentence!",
        content_type="text",
        episode_type="message",
        created_at="2026-03-06T00:00:00Z",
        metadata_json='{"topic":"food"}',
        filterable_metadata_json=None,
        deleted=0,
    )


def test_sentence_chunking_splits_episode_content():
    pipeline = DerivativePipeline(
        graph_store=None,  # type: ignore[arg-type]
        derivative_index=None,  # type: ignore[arg-type]
        embedder=fake_embedder,
    )

    chunks = pipeline.chunk_text("First sentence. Second sentence!\nThird line")

    assert chunks == ["First sentence.", "Second sentence!", "Third line"]


def test_derivative_metadata_mapping_preserves_source_fields():
    pipeline = DerivativePipeline(
        graph_store=None,  # type: ignore[arg-type]
        derivative_index=None,  # type: ignore[arg-type]
        embedder=fake_embedder,
    )

    metadata = pipeline.build_derivative_metadata(
        episode=build_episode(),
        chunk_index=2,
        chunk_count=3,
    )

    assert metadata["episode_uid"] == "ep-1"
    assert metadata["producer_role"] == "user"
    assert metadata["chunk_index"] == 2
    assert metadata["chunk_count"] == 3
    assert metadata["source_metadata"] == {"topic": "food"}


@pytest.mark.anyio
async def test_derivative_pipeline_writes_vectors_and_graph(tmp_path: Path):
    sqlite_factory = SqliteEngineFactory(
        Settings(sqlite_path=tmp_path / "memolite.sqlite3")
    )
    await sqlite_factory.initialize_schema()
    derivative_index = SqliteVecIndex(sqlite_factory, "derivative_feature_vectors")
    kuzu_engine = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "graph.kuzu"))
    await kuzu_engine.initialize_schema()
    graph_store = KuzuGraphStore(kuzu_engine)
    pipeline = DerivativePipeline(
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=fake_embedder,
    )

    derivatives = await pipeline.create_derivatives(build_episode())
    derivative_nodes = await graph_store.get_nodes(
        node_table="Derivative",
        uids=[record.uid for record in derivatives],
    )
    related_episodes = await graph_store.search_related_nodes(
        source_table="Derivative",
        source_uid=derivatives[0].uid,
        relation_table="DERIVED_FROM",
        target_table="Episode",
    )
    search_hits = await derivative_index.search_top_k([15.0, 1.0], limit=2)
    engine = sqlite_factory.create_engine()
    async with engine.connect() as conn:
        vector_rows = (
            await conn.exec_driver_sql(
                "SELECT feature_id, embedding FROM derivative_feature_vectors "
                "ORDER BY feature_id"
            )
        ).all()

    assert [record.uid for record in derivatives] == ["ep-1:d:1", "ep-1:d:2"]
    assert [node.properties["uid"] for node in derivative_nodes] == [
        "ep-1:d:1",
        "ep-1:d:2",
    ]
    assert [node.properties["uid"] for node in related_episodes] == ["ep-1"]
    assert len(search_hits) == 2
    assert len(vector_rows) == 2
    assert json.loads(derivatives[0].metadata_json)["source_metadata"] == {
        "topic": "food"
    }

    await kuzu_engine.close()
    await sqlite_factory.dispose()
