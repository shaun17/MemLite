from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.episodic.delete import EpisodicDeleteService
from memlite.episodic.derivative_pipeline import DerivativePipeline
from memlite.episodic.search import EpisodicSearchService
from memlite.storage.episode_store import SqliteEpisodeStore
from memlite.storage.graph_store import KuzuGraphStore
from memlite.storage.kuzu_engine import KuzuEngineFactory
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.sqlite_vec import SqliteVecIndex


async def fake_embedder(text: str) -> list[float]:
    if "ramen" in text or "food" in text:
        return [1.0, 0.0]
    return [0.0, 1.0]


@pytest.mark.anyio
async def test_delete_episode_leaves_no_search_residue(tmp_path: Path):
    sqlite_factory = SqliteEngineFactory(
        Settings(sqlite_path=tmp_path / "memlite.sqlite3")
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
                "content": "Ramen is my favorite food.",
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

    before = await search_service.search(query="food ramen", session_id="session-a")
    await delete_service.delete_episode_uids(["ep-1"])
    after = await search_service.search(query="food ramen", session_id="session-a")

    assert [match.episode.uid for match in before.matches] == ["ep-1"]
    assert after.matches == []
    assert after.expanded_context == []

    await kuzu_engine.close()
    await sqlite_factory.dispose()
