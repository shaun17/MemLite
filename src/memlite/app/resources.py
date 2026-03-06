"""Application resource manager bootstrap."""

from dataclasses import dataclass, field

from memlite.common.config import Settings
from memlite.episodic.delete import EpisodicDeleteService
from memlite.episodic.derivative_pipeline import DerivativePipeline
from memlite.episodic.search import EpisodicSearchService
from memlite.memory.config_service import MemoryConfigService
from memlite.metrics.service import MetricsService
from memlite.orchestrator.memory_orchestrator import MemoryOrchestrator
from memlite.semantic.service import SemanticService
from memlite.semantic.session_manager import SemanticSessionManager
from memlite.storage.episode_store import SqliteEpisodeStore
from memlite.storage.graph_store import KuzuGraphStore
from memlite.storage.kuzu_engine import KuzuEngineFactory
from memlite.storage.project_store import SqliteProjectStore
from memlite.storage.semantic_config_store import SqliteSemanticConfigStore
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.sqlite_vec import SqliteVecIndex


async def default_embedder(text: str) -> list[float]:
    """Return a deterministic lightweight embedding."""
    lowered = text.lower()
    keywords = (
        ("food", "ramen", "meal", "taste"),
        ("travel", "seat", "flight", "trip"),
        ("work", "project", "task", "deadline"),
        ("profile", "name", "preference", "like"),
    )
    return [1.0 if any(word in lowered for word in bucket) else 0.0 for bucket in keywords]


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
    _initialized: bool = field(default=False, init=False, repr=False)

    @classmethod
    def create(cls, settings: Settings) -> "ResourceManager":
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
        derivative_pipeline = DerivativePipeline(
            graph_store=graph_store,
            derivative_index=derivative_index,
            embedder=default_embedder,
        )
        episodic_search = EpisodicSearchService(
            episode_store=episode_store,
            graph_store=graph_store,
            derivative_index=derivative_index,
            embedder=default_embedder,
            metrics=metrics,
        )
        episodic_delete = EpisodicDeleteService(
            episode_store=episode_store,
            graph_store=graph_store,
            derivative_index=derivative_index,
        )
        semantic_service = SemanticService(
            feature_store=semantic_feature_store,
            config_store=semantic_config_store,
            embedder=default_embedder,
            default_category_resolver=lambda _set_id: [],
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
        return cls(
            settings=settings,
            metrics=metrics,
            memory_config=MemoryConfigService(),
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
        )

    async def initialize(self) -> None:
        """Initialize backing stores and schemas."""
        if self._initialized:
            return
        await self.sqlite.initialize_schema()
        await self.semantic_feature_store.initialize()
        await self.derivative_index.initialize()
        await self.kuzu.initialize_schema()
        self._initialized = True

    async def close(self) -> None:
        """Close backing resources."""
        if not self._initialized:
            return
        await self.kuzu.close()
        await self.sqlite.dispose()
        self._initialized = False
