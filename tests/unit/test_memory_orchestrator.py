from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.episodic.delete import EpisodicDeleteService
from memlite.episodic.derivative_pipeline import DerivativePipeline
from memlite.episodic.search import EpisodicSearchService
from memlite.orchestrator.memory_orchestrator import MemoryOrchestrator
from memlite.semantic.service import SemanticService
from memlite.storage.episode_store import SqliteEpisodeStore
from memlite.storage.graph_store import KuzuGraphStore
from memlite.storage.kuzu_engine import KuzuEngineFactory
from memlite.storage.project_store import SqliteProjectStore
from memlite.storage.semantic_config_store import SqliteSemanticConfigStore
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.sqlite_vec import SqliteVecIndex


async def fake_embedder(text: str) -> list[float]:
    lowered = text.lower()
    if "ramen" in lowered or "food" in lowered:
        return [1.0, 0.0]
    return [0.0, 1.0]


async def identity_reranker(_query, matches):
    return matches


async def prepare_orchestrator(tmp_path: Path) -> tuple[MemoryOrchestrator, SqliteSemanticFeatureStore]:
    sqlite_factory = SqliteEngineFactory(
        Settings(sqlite_path=tmp_path / "memlite.sqlite3")
    )
    await sqlite_factory.initialize_schema()
    project_store = SqliteProjectStore(sqlite_factory)
    session_store = SqliteSessionStore(sqlite_factory)
    episode_store = SqliteEpisodeStore(sqlite_factory)
    semantic_config_store = SqliteSemanticConfigStore(sqlite_factory)
    semantic_feature_store = SqliteSemanticFeatureStore(sqlite_factory)
    await semantic_feature_store.initialize()
    derivative_index = SqliteVecIndex(sqlite_factory, "derivative_feature_vectors")
    kuzu_engine = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "graph.kuzu"))
    await kuzu_engine.initialize_schema()
    graph_store = KuzuGraphStore(kuzu_engine)
    derivative_pipeline = DerivativePipeline(
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=fake_embedder,
    )
    episodic_search_service = EpisodicSearchService(
        episode_store=episode_store,
        graph_store=graph_store,
        derivative_index=derivative_index,
        embedder=fake_embedder,
        reranker=identity_reranker,
    )
    episodic_delete_service = EpisodicDeleteService(
        episode_store=episode_store,
        graph_store=graph_store,
        derivative_index=derivative_index,
    )
    semantic_service = SemanticService(
        feature_store=semantic_feature_store,
        config_store=semantic_config_store,
        embedder=fake_embedder,
        default_category_resolver=lambda _set_id: [],
    )
    orchestrator = MemoryOrchestrator(
        project_store=project_store,
        session_store=session_store,
        episode_store=episode_store,
        semantic_feature_store=semantic_feature_store,
        semantic_service=semantic_service,
        episodic_search_service=episodic_search_service,
        episodic_delete_service=episodic_delete_service,
        derivative_pipeline=derivative_pipeline,
    )
    await orchestrator.create_project(org_id="org-a", project_id="project-a")
    await orchestrator.create_session(
        session_key="session-a",
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
        user_id="user-1",
    )
    return orchestrator, semantic_feature_store


@pytest.mark.anyio
async def test_orchestrator_routes_auto_mode_and_short_term_context(tmp_path: Path):
    orchestrator, semantic_feature_store = await prepare_orchestrator(tmp_path)
    await orchestrator.add_episodes(
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
                "content": "I love ramen.",
                "content_type": "text",
                "episode_type": "message",
            }
        ],
    )
    await semantic_feature_store.add_feature(
        set_id="session-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0],
    )

    response = await orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
        mode="auto",
    )

    assert response.mode == "mixed"
    assert response.short_term_context.startswith("user: I love ramen.")
    assert [item.source for item in response.combined] == ["episodic", "semantic"]


@pytest.mark.anyio
async def test_orchestrator_mixed_retrieval_and_agent_mode(tmp_path: Path):
    orchestrator, semantic_feature_store = await prepare_orchestrator(tmp_path)
    await orchestrator.add_episodes(
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
                "content_type": "text",
                "episode_type": "message",
            }
        ],
    )
    await semantic_feature_store.add_feature(
        set_id="session-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0],
    )

    agent = await orchestrator.agent_mode(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
    )

    assert agent.search.mode == "mixed"
    assert "[episodic]" in agent.context_text
    assert "[semantic]" in agent.context_text


@pytest.mark.anyio
async def test_orchestrator_delete_episode_triggers_semantic_cleanup(tmp_path: Path):
    orchestrator, semantic_feature_store = await prepare_orchestrator(tmp_path)
    await orchestrator.add_episodes(
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
                "content_type": "text",
                "episode_type": "message",
            }
        ],
    )
    feature_id = await semantic_feature_store.add_feature(
        set_id="session-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0],
    )
    await semantic_feature_store.add_citations(feature_id, ["ep-1"])

    await orchestrator.delete_episodes(
        episode_uids=["ep-1"],
        semantic_set_id="session-a",
    )

    feature = await semantic_feature_store.get_feature(feature_id)
    history_count = await semantic_feature_store.get_history_messages_count(
        set_ids=["session-a"],
        is_ingested=None,
    )

    assert feature is not None
    assert feature.deleted == 1
    assert history_count == 0


@pytest.mark.anyio
async def test_orchestrator_project_and_session_cascade_delete(tmp_path: Path):
    orchestrator, semantic_feature_store = await prepare_orchestrator(tmp_path)
    await orchestrator.add_episodes(
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
                "content_type": "text",
                "episode_type": "message",
            }
        ],
    )
    await semantic_feature_store.add_feature(
        set_id="session-a",
        category="profile",
        tag="food",
        feature_name="favorite_food",
        value="ramen",
        embedding=[1.0, 0.0],
    )

    await orchestrator.delete_project(org_id="org-a", project_id="project-a")

    project = await orchestrator.get_project(org_id="org-a", project_id="project-a")
    sessions = await orchestrator.search_sessions(project_id="project-a")
    features = await semantic_feature_store.get_feature_set(set_id="session-a")

    assert project is None
    assert sessions == []
    assert features == []
