from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.episodic.delete import EpisodicDeleteService
from memlite.episodic.derivative_pipeline import DerivativePipeline
from memlite.episodic.search import EpisodicSearchService
from memlite.orchestrator.memory_orchestrator import MemoryOrchestrator
from memlite.semantic.service import SemanticService
from memlite.semantic.service import SemanticIngestionWorker
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


@pytest.mark.anyio
async def test_memory_orchestrator_mixed_retrieval_e2e(tmp_path: Path):
    sqlite_factory = SqliteEngineFactory(
        Settings(sqlite_path=tmp_path / "memolite.sqlite3")
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

    search = await orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
    )
    agent = await orchestrator.agent_mode(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
    )

    assert search.mode == "mixed"
    assert [item.source for item in search.combined] == ["episodic", "semantic"]
    assert "user: Ramen is my favorite food." in search.short_term_context
    assert "[episodic] Ramen is my favorite food." in agent.context_text
    assert "[semantic] ramen" in agent.context_text

    await kuzu_engine.close()
    await sqlite_factory.dispose()


@pytest.mark.anyio
async def test_add_memory_then_semantic_ingestion_then_recall(tmp_path: Path):
    sqlite_factory = SqliteEngineFactory(
        Settings(sqlite_path=tmp_path / "memolite.sqlite3")
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

    async def processor(set_id: str, history_ids: list[str]) -> int:
        assert set_id == "session-a"
        assert history_ids == ["ep-1"]
        await semantic_feature_store.add_feature(
            set_id=set_id,
            category="profile",
            tag="food",
            feature_name="favorite_food",
            value="ramen",
            embedding=await semantic_service.generate_feature_embedding("food ramen"),
        )
        return len(history_ids)

    worker = SemanticIngestionWorker(
        feature_store=semantic_feature_store,
        processor=processor,
    )
    processed = await worker.process_pending("session-a")
    search = await orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
        mode="semantic",
    )

    assert processed == 1
    assert search.mode == "semantic"
    assert [item.source for item in search.combined] == ["semantic"]
    assert search.combined[0].content == "ramen"

    await kuzu_engine.close()
    await sqlite_factory.dispose()
