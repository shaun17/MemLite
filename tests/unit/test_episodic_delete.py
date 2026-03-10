from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.episodic.delete import EpisodicDeleteService
from memolite.episodic.derivative_pipeline import DerivativePipeline, vector_item_id
from memolite.episodic.search import EpisodicSearchService
from memolite.storage.episode_store import SqliteEpisodeStore
from memolite.storage.graph_store import KuzuGraphStore
from memolite.storage.kuzu_engine import KuzuEngineFactory
from memolite.storage.session_store import SqliteSessionStore
from memolite.storage.sqlite_engine import SqliteEngineFactory
from memolite.storage.sqlite_vec import SqliteVecIndex


async def fake_embedder(text: str) -> list[float]:
    if "ramen" in text or "food" in text:
        return [1.0, 0.0]
    return [0.0, 1.0]


async def prepare_delete_fixture(tmp_path: Path):
    sqlite_factory = SqliteEngineFactory(
        Settings(sqlite_path=tmp_path / "memolite.sqlite3")
    )
    await sqlite_factory.initialize_schema()
    session_store = SqliteSessionStore(sqlite_factory)
    await session_store.create_session(
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
        session_key="session-a",
        user_id="user-1",
    )
    episode_store = SqliteEpisodeStore(sqlite_factory)
    await episode_store.add_episodes(
        [
            {
                "uid": "ep-1",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 1,
                "content": "I love ramen. It is my favorite food.",
                "content_type": "text",
                "episode_type": "message",
            },
            {
                "uid": "ep-2",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "assistant-1",
                "producer_role": "assistant",
                "sequence_num": 2,
                "content": "I will remember that preference.",
                "content_type": "text",
                "episode_type": "message",
            },
        ]
    )
    derivative_index = SqliteVecIndex(sqlite_factory, "derivative_feature_vectors")
    kuzu_engine = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "graph.kuzu"))
    await kuzu_engine.initialize_schema()
    graph_store = KuzuGraphStore(kuzu_engine)
    pipeline = DerivativePipeline(
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=fake_embedder,
    )
    for episode in await episode_store.list_episodes(session_key="session-a"):
        await pipeline.create_derivatives(episode)

    search_service = EpisodicSearchService(
        episode_store=episode_store,
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=fake_embedder,
    )
    delete_service = EpisodicDeleteService(
        episode_store=episode_store,
        graph_store=graph_store,
        derivative_index=derivative_index,
    )
    return sqlite_factory, kuzu_engine, episode_store, graph_store, derivative_index, search_service, delete_service


@pytest.mark.anyio
async def test_delete_cleanup_removes_vectors_and_graph_nodes(tmp_path: Path):
    (
        sqlite_factory,
        kuzu_engine,
        episode_store,
        graph_store,
        derivative_index,
        search_service,
        delete_service,
    ) = await prepare_delete_fixture(tmp_path)

    before = await search_service.search(query="food ramen", session_id="session-a")
    summary = await delete_service.delete_episode_uids(["ep-1"])
    after = await search_service.search(query="food ramen", session_id="session-a")
    derivative_nodes = await graph_store.get_nodes(
        node_table="Derivative",
        uids=summary.derivative_uids,
    )
    engine = sqlite_factory.create_engine()
    async with engine.connect() as conn:
        vector_rows = (
            await conn.exec_driver_sql(
                "SELECT feature_id FROM derivative_feature_vectors ORDER BY feature_id"
            )
        ).all()
    remaining_episodes = await episode_store.list_episodes(
        session_key="session-a",
        include_deleted=False,
    )

    assert [match.episode.uid for match in before.matches] == ["ep-1"]
    assert summary.episode_uids == ["ep-1"]
    assert summary.derivative_uids
    assert after.matches == []
    assert derivative_nodes == []
    assert {
        vector_item_id(derivative_uid) for derivative_uid in summary.derivative_uids
    }.isdisjoint({int(row[0]) for row in vector_rows})
    assert [episode.uid for episode in remaining_episodes] == ["ep-2"]

    await kuzu_engine.close()
    await sqlite_factory.dispose()


@pytest.mark.anyio
async def test_delete_matching_episodes_uses_filters(tmp_path: Path):
    (
        sqlite_factory,
        kuzu_engine,
        episode_store,
        _graph_store,
        _derivative_index,
        _search_service,
        delete_service,
    ) = await prepare_delete_fixture(tmp_path)

    summary = await delete_service.delete_matching_episodes(
        session_key="session-a",
        producer_role="assistant",
        episode_type="message",
    )
    remaining = await episode_store.list_episodes(
        session_key="session-a",
        include_deleted=False,
    )

    assert summary.episode_uids == ["ep-2"]
    assert [episode.uid for episode in remaining] == ["ep-1"]

    await kuzu_engine.close()
    await sqlite_factory.dispose()
