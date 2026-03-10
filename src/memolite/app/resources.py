"""Application resource manager bootstrap."""

import hashlib
import math
import re
from dataclasses import dataclass, field

from memolite.app.background import BackgroundTaskRunner
from memolite.common.config import Settings
from memolite.episodic.delete import EpisodicDeleteService
from memolite.episodic.derivative_pipeline import DerivativePipeline
from memolite.episodic.search import EpisodicSearchService
from memolite.memory.config_service import MemoryConfigService
from memolite.metrics.service import MetricsService
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


_TOKEN_PATTERN = re.compile(r"[\w\-']+")


async def default_embedder(text: str) -> list[float]:
    """Return a deterministic lightweight embedding.

    This is still a local fallback embedder, but unlike the previous keyword
    bucket implementation it supports open-vocabulary text via hashed token
    projections.
    """
    dimensions = 64
    vector = [0.0] * dimensions
    lowered = text.lower()
    tokens = _TOKEN_PATTERN.findall(lowered)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


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
            embedder=default_embedder,
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
            background_tasks=None,  # type: ignore[arg-type]
        )
        resources.background_tasks = BackgroundTaskRunner(resources=resources)
        return resources

    async def initialize(self) -> None:
        """Initialize backing stores and schemas."""
        if self._initialized:
            return
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
