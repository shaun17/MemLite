"""Application resource manager bootstrap."""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from memolite.app.background import BackgroundTaskRunner
from memolite.common.config import Settings
from memolite.embedders import create_embedder
from memolite.embedders.base import EmbedderProvider
from memolite.episodic.delete import EpisodicDeleteService
from memolite.episodic.derivative_pipeline import DerivativePipeline
from memolite.episodic.search import EpisodicSearchService
from memolite.memory.config_service import MemoryConfigService
from memolite.metrics.service import MetricsService
from memolite.rerankers import create_reranker
from memolite.rerankers.base import RerankerProvider
from memolite.orchestrator.memory_orchestrator import MemoryOrchestrator
from memolite.semantic.service import SemanticService
from memolite.semantic.session_manager import SemanticSessionManager
from memolite.storage.episode_store import SqliteEpisodeStore
from memolite.storage.graph_store import KuzuGraphStore
from memolite.storage.kuzu_engine import KuzuEngineFactory
from memolite.storage.project_store import SqliteProjectStore
from memolite.storage.semantic_config_store import SqliteSemanticConfigStore
from memolite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memolite.storage.session_store import SqliteSessionStore
from memolite.storage.sqlite_engine import SqliteEngineFactory
from memolite.storage.sqlite_vec import SqliteVecIndex


def _resolve_embedder_provider_name(settings: Settings) -> str:
    """Resolve the embedder provider name from settings or persisted set config.

    Current behavior keeps the selection intentionally simple: if the SQLite DB
    already contains exactly one distinct non-empty embedder_name across set
    configs, treat it as the global provider override. Otherwise fall back to
    settings.embedder_provider.
    """
    db_path = Path(settings.sqlite_path)
    if not db_path.exists():
        return settings.embedder_provider
    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='semantic_config_set_id_resources'"
            ).fetchone()
            if row is None:
                return settings.embedder_provider
            rows = conn.execute(
                """
                SELECT DISTINCT embedder_name
                FROM semantic_config_set_id_resources
                WHERE embedder_name IS NOT NULL AND TRIM(embedder_name) != ''
                ORDER BY embedder_name
                """
            ).fetchall()
    except sqlite3.Error:
        return settings.embedder_provider

    provider_names = [str(row[0]) for row in rows]
    if len(provider_names) == 1:
        return provider_names[0]
    return settings.embedder_provider


@dataclass
class ResourceManager:
    """Bootstrap runtime singleton-like services."""

    settings: Settings
    metrics: MetricsService
    memory_config: MemoryConfigService
    sqlite: SqliteEngineFactory
    kuzu: KuzuEngineFactory
    project_store: SqliteProjectStore
    session_store: SqliteSessionStore
    episode_store: SqliteEpisodeStore
    semantic_config_store: SqliteSemanticConfigStore
    semantic_feature_store: SqliteSemanticFeatureStore
    derivative_index: SqliteVecIndex
    graph_store: KuzuGraphStore
    derivative_pipeline: DerivativePipeline
    episodic_search: EpisodicSearchService
    episodic_delete: EpisodicDeleteService
    semantic_service: SemanticService
    semantic_session_manager: SemanticSessionManager
    orchestrator: MemoryOrchestrator
    background_tasks: BackgroundTaskRunner
    embedder_provider_name: str
    _embedder_provider: EmbedderProvider = field(repr=False)
    _reranker_provider: RerankerProvider | None = field(default=None, repr=False)
    _initialized: bool = field(default=False, init=False, repr=False)

    @classmethod
    def create(cls, settings: Settings) -> "ResourceManager":
        # Resource wiring stays in one place so API, MCP and CLI all reuse the
        # exact same runtime graph and recovery hooks.
        sqlite = SqliteEngineFactory(settings)
        kuzu = KuzuEngineFactory(settings)
        metrics = MetricsService()
        kuzu.bind_metrics(metrics)
        project_store = SqliteProjectStore(sqlite)
        session_store = SqliteSessionStore(sqlite)
        episode_store = SqliteEpisodeStore(sqlite)
        semantic_config_store = SqliteSemanticConfigStore(sqlite)
        semantic_feature_store = SqliteSemanticFeatureStore(sqlite)
        derivative_index = SqliteVecIndex(sqlite, "derivative_feature_vectors")
        derivative_index.bind_metrics(metrics)
        graph_store = KuzuGraphStore(kuzu)
        embedder_provider_name = _resolve_embedder_provider_name(settings)
        embedder_settings = settings.model_copy(update={"embedder_provider": embedder_provider_name})
        embedder_provider = create_embedder(embedder_settings)
        embedder_fn = embedder_provider.as_embedder_fn()
        memory_config = MemoryConfigService()
        reranker_provider = create_reranker(settings)
        reranker_fn = reranker_provider.as_reranker_fn() if reranker_provider else None
        derivative_pipeline = DerivativePipeline(
            graph_store=graph_store,
            derivative_index=derivative_index,
            embedder=embedder_fn,
        )
        episodic_search = EpisodicSearchService(
            episode_store=episode_store,
            graph_store=graph_store,
            derivative_index=derivative_index,
            embedder=embedder_fn,
            reranker=reranker_fn,
            rerank_enabled_getter=lambda: memory_config.get_episodic().rerank_enabled,
            metrics=metrics,
            candidate_multiplier=settings.episodic_search_candidate_multiplier,
            max_candidates=settings.episodic_search_max_candidates,
        )
        episodic_delete = EpisodicDeleteService(
            episode_store=episode_store,
            graph_store=graph_store,
            derivative_index=derivative_index,
        )
        semantic_service = SemanticService(
            feature_store=semantic_feature_store,
            config_store=semantic_config_store,
            embedder=embedder_fn,
            default_category_resolver=lambda _set_id: [],
            candidate_multiplier=settings.semantic_search_candidate_multiplier,
            max_candidates=settings.semantic_search_max_candidates,
        )
        semantic_session_manager = SemanticSessionManager(semantic_config_store)
        orchestrator = MemoryOrchestrator(
            project_store=project_store,
            session_store=session_store,
            episode_store=episode_store,
            semantic_feature_store=semantic_feature_store,
            semantic_service=semantic_service,
            episodic_search_service=episodic_search,
            episodic_delete_service=episodic_delete,
            derivative_pipeline=derivative_pipeline,
        )
        resources = cls(
            settings=settings,
            metrics=metrics,
            memory_config=memory_config,
            sqlite=sqlite,
            kuzu=kuzu,
            project_store=project_store,
            session_store=session_store,
            episode_store=episode_store,
            semantic_config_store=semantic_config_store,
            semantic_feature_store=semantic_feature_store,
            derivative_index=derivative_index,
            graph_store=graph_store,
            derivative_pipeline=derivative_pipeline,
            episodic_search=episodic_search,
            episodic_delete=episodic_delete,
            semantic_service=semantic_service,
            semantic_session_manager=semantic_session_manager,
            orchestrator=orchestrator,
            background_tasks=None,  # type: ignore[arg-type]
            embedder_provider_name=embedder_provider_name,
            _embedder_provider=embedder_provider,
            _reranker_provider=reranker_provider,
        )
        resources.background_tasks = BackgroundTaskRunner(resources=resources)
        return resources

    async def initialize(self) -> None:
        """Initialize backing stores and schemas."""
        if self._initialized:
            return
        await self._embedder_provider.warm_up()
        if self._reranker_provider is not None:
            await self._reranker_provider.warm_up()
        if self.embedder_provider_name == "hash":
            try:
                import jieba
                jieba.initialize()
            except (ImportError, OSError):
                pass
        await self.sqlite.initialize_schema()
        await self.semantic_feature_store.initialize()
        await self.derivative_index.initialize()
        await self.kuzu.initialize_schema()
        await self.background_tasks.run_startup_recovery()
        self._initialized = True

    async def close(self) -> None:
        """Close backing resources."""
        if not self._initialized:
            return
        await self.kuzu.close()
        await self.sqlite.dispose()
        self._initialized = False
