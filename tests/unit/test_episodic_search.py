from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.episodic.derivative_pipeline import DerivativePipeline
from memlite.episodic.search import EpisodicSearchService, _candidate_limit
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


async def prepare_search_fixture(tmp_path: Path) -> EpisodicSearchService:
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
            {
                "uid": "ep-3",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 3,
                "content": "I also prefer aisle seats.",
                "content_type": "text",
                "episode_type": "message",
            },
            {
                "uid": "ep-4",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 4,
                "content": "Ramen is also a comfort food.",
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

    return EpisodicSearchService(
        episode_store=episode_store,
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=fake_embedder,
    )


@pytest.mark.anyio
async def test_episodic_similarity_search_returns_expected_episode(tmp_path: Path):
    service = await prepare_search_fixture(tmp_path)

    results = await service.search(query="food ramen", session_id="session-a", limit=1)

    assert [match.episode.uid for match in results.matches] == ["ep-1"]


@pytest.mark.anyio
async def test_episodic_search_applies_filters_and_context_expansion(tmp_path: Path):
    service = await prepare_search_fixture(tmp_path)

    results = await service.search(
        query="food ramen",
        session_id="session-a",
        producer_role="user",
        episode_type="message",
        context_window=1,
        limit=1,
    )

    assert [match.episode.uid for match in results.matches] == ["ep-1"]
    assert [episode.uid for episode in results.expanded_context] == ["ep-1", "ep-2"]


@pytest.mark.anyio
async def test_episodic_search_respects_score_threshold(tmp_path: Path):
    service = await prepare_search_fixture(tmp_path)

    results = await service.search(
        query="food ramen",
        session_id="session-a",
        min_score=1.01,
    )

    assert results.matches == []
    assert results.expanded_context == []


@pytest.mark.anyio
async def test_episodic_search_reranker_can_override_default_order(tmp_path: Path):
    base_service = await prepare_search_fixture(tmp_path)

    async def reverse_reranker(_query, matches):
        return list(reversed(matches))

    reranked_service = EpisodicSearchService(
        episode_store=base_service._episode_store,
        graph_store=base_service._graph_store,
        derivative_index=base_service._derivative_index,
        embedder=fake_embedder,
        reranker=reverse_reranker,
    )

    results = await reranked_service.search(query="food ramen", session_id="session-a")

    assert [match.episode.uid for match in results.matches] == ["ep-4", "ep-1"]


@pytest.mark.anyio
async def test_episodic_search_returns_stable_chronology_for_equal_scores(tmp_path: Path):
    service = await prepare_search_fixture(tmp_path)

    results = await service.search(query="food ramen", session_id="session-a")

    assert [match.episode.uid for match in results.matches] == ["ep-1", "ep-4"]


@pytest.mark.anyio
async def test_episodic_search_result_structure_is_stable(tmp_path: Path):
    service = await prepare_search_fixture(tmp_path)

    results = await service.search(query="food ramen", session_id="session-a", limit=1)

    assert len(results.matches) == 1
    assert results.matches[0].episode.uid == "ep-1"
    assert results.matches[0].derivative_uid.startswith("ep-1:d:")
    assert isinstance(results.matches[0].score, float)
    assert [episode.uid for episode in results.expanded_context] == ["ep-1", "ep-2"]


def test_episodic_candidate_limit_respects_max_candidates():
    assert _candidate_limit(limit=5, multiplier=4, max_candidates=12) == 12
    assert _candidate_limit(limit=2, multiplier=4, max_candidates=20) == 8
