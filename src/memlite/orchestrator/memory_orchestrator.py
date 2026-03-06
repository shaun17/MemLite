"""Unified orchestration for project, session, episodic and semantic memory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from memlite.episodic.delete import EpisodicDeleteService
from memlite.episodic.derivative_pipeline import DerivativePipeline
from memlite.episodic.search import EpisodicSearchResult, EpisodicSearchService
from memlite.memory.short_term_memory import ShortTermMemory, ShortTermMessage
from memlite.semantic.service import SemanticSearchResult, SemanticService
from memlite.storage.episode_store import EpisodeRecord, SqliteEpisodeStore
from memlite.storage.project_store import ProjectRecord, SqliteProjectStore
from memlite.storage.semantic_feature_store import SqliteSemanticFeatureStore
from memlite.storage.session_store import SessionRecord, SqliteSessionStore

SearchMode = Literal["auto", "episodic", "semantic", "mixed"]
QueryRewriteFn = Callable[[str], Awaitable[str]]
QuerySplitFn = Callable[[str], Awaitable[list[str]]]
SetIdResolver = Callable[[SessionRecord], str]


async def _identity_rewrite(query: str) -> str:
    return query


async def _single_split(query: str) -> list[str]:
    return [query]


def _default_set_id(session: SessionRecord) -> str:
    return session.session_key


@dataclass(slots=True)
class CombinedMemoryItem:
    """Merged retrieval item across memory sources."""

    source: Literal["episodic", "semantic"]
    content: str
    identifier: str
    score: float


@dataclass(slots=True)
class MemorySearchResponse:
    """Unified orchestrator search response."""

    mode: SearchMode
    rewritten_query: str
    subqueries: list[str]
    episodic: EpisodicSearchResult | None
    semantic: SemanticSearchResult | None
    combined: list[CombinedMemoryItem]
    short_term_context: str


@dataclass(slots=True)
class AgentModeResponse:
    """Agent-facing aggregation response."""

    search: MemorySearchResponse
    context_text: str


class MemoryOrchestrator:
    """Coordinate memory lifecycle and retrieval across all stores."""

    def __init__(
        self,
        *,
        project_store: SqliteProjectStore,
        session_store: SqliteSessionStore,
        episode_store: SqliteEpisodeStore,
        semantic_feature_store: SqliteSemanticFeatureStore,
        semantic_service: SemanticService,
        episodic_search_service: EpisodicSearchService,
        episodic_delete_service: EpisodicDeleteService,
        derivative_pipeline: DerivativePipeline,
        query_rewriter: QueryRewriteFn = _identity_rewrite,
        query_splitter: QuerySplitFn = _single_split,
        set_id_resolver: SetIdResolver = _default_set_id,
        short_term_capacity: int = 4096,
    ) -> None:
        self._project_store = project_store
        self._session_store = session_store
        self._episode_store = episode_store
        self._semantic_feature_store = semantic_feature_store
        self._semantic_service = semantic_service
        self._episodic_search_service = episodic_search_service
        self._episodic_delete_service = episodic_delete_service
        self._derivative_pipeline = derivative_pipeline
        self._query_rewriter = query_rewriter
        self._query_splitter = query_splitter
        self._set_id_resolver = set_id_resolver
        self._short_term_capacity = short_term_capacity

    async def create_project(
        self,
        *,
        org_id: str,
        project_id: str,
        description: str | None = None,
    ) -> None:
        await self._project_store.create_project(org_id, project_id, description)

    async def get_project(
        self,
        *,
        org_id: str,
        project_id: str,
    ) -> ProjectRecord | None:
        return await self._project_store.get_project(org_id, project_id)

    async def list_projects(self, org_id: str | None = None) -> list[ProjectRecord]:
        return await self._project_store.list_projects(org_id)

    async def create_session(
        self,
        *,
        session_key: str,
        org_id: str,
        project_id: str,
        session_id: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        group_id: str | None = None,
    ) -> None:
        await self._session_store.create_session(
            session_key=session_key,
            org_id=org_id,
            project_id=project_id,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            group_id=group_id,
        )

    async def get_session(self, session_key: str) -> SessionRecord | None:
        return await self._session_store.get_session(session_key)

    async def search_sessions(self, **filters: str | None) -> list[SessionRecord]:
        return await self._session_store.search_sessions(**filters)

    async def add_episodes(
        self,
        *,
        session_key: str,
        episodes: list[dict[str, object | None]],
        semantic_set_id: str | None = None,
    ) -> list[EpisodeRecord]:
        await self._episode_store.add_episodes(episodes)
        persisted = await self._episode_store.get_episodes(
            [str(payload["uid"]) for payload in episodes]
        )
        for episode in persisted:
            await self._derivative_pipeline.create_derivatives(episode)
        if semantic_set_id is not None:
            for episode in persisted:
                await self._semantic_feature_store.add_history_to_set(
                    semantic_set_id,
                    episode.uid,
                )

        short_term = await ShortTermMemory.create(
            session_key=session_key,
            session_store=self._session_store,
            message_capacity=self._short_term_capacity,
        )
        await short_term.add_messages(
            [
                ShortTermMessage(
                    uid=episode.uid,
                    content=episode.content,
                    producer_id=episode.producer_id,
                    producer_role=episode.producer_role,
                    created_at=episode.created_at,
                )
                for episode in persisted
            ]
        )
        return persisted

    async def search_memories(
        self,
        *,
        query: str,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: SearchMode = "auto",
        limit: int = 5,
        context_window: int = 1,
        min_score: float = 0.0001,
        producer_role: str | None = None,
        episode_type: str | None = None,
    ) -> MemorySearchResponse:
        rewritten_query = await self._query_rewriter(query)
        subqueries = await self._query_splitter(rewritten_query)
        resolved_mode = self._resolve_mode(
            requested_mode=mode,
            session_id=session_id,
            semantic_set_id=semantic_set_id,
        )
        episodic_result: EpisodicSearchResult | None = None
        semantic_result: SemanticSearchResult | None = None

        if resolved_mode in {"episodic", "mixed"}:
            episodic_result = await self._search_episodic_queries(
                subqueries=subqueries,
                session_id=session_id,
                producer_role=producer_role,
                episode_type=episode_type,
                limit=limit,
                context_window=context_window,
                min_score=min_score,
            )
        if resolved_mode in {"semantic", "mixed"}:
            semantic_result = await self._search_semantic_queries(
                subqueries=subqueries,
                semantic_set_id=semantic_set_id,
                limit=limit,
            )

        short_term_context = ""
        if session_key is not None:
            short_term_context = await self._build_short_term_context(session_key)

        return MemorySearchResponse(
            mode=resolved_mode,
            rewritten_query=rewritten_query,
            subqueries=subqueries,
            episodic=episodic_result,
            semantic=semantic_result,
            combined=self._merge_results(
                episodic_result=episodic_result,
                semantic_result=semantic_result,
            ),
            short_term_context=short_term_context,
        )

    async def agent_mode(
        self,
        *,
        query: str,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: SearchMode = "auto",
        limit: int = 5,
        context_window: int = 1,
    ) -> AgentModeResponse:
        search = await self.search_memories(
            query=query,
            session_key=session_key,
            session_id=session_id,
            semantic_set_id=semantic_set_id,
            mode=mode,
            limit=limit,
            context_window=context_window,
        )
        sections: list[str] = []
        if search.short_term_context:
            sections.append(search.short_term_context)
        for item in search.combined:
            sections.append(f"[{item.source}] {item.content}")
        return AgentModeResponse(
            search=search,
            context_text="\n".join(sections),
        )

    async def delete_episodes(
        self,
        *,
        episode_uids: list[str],
        semantic_set_id: str | None = None,
    ) -> None:
        await self._episodic_delete_service.delete_episode_uids(episode_uids)
        await self._cleanup_semantic_history(
            semantic_set_id=semantic_set_id,
            history_ids=episode_uids,
        )

    async def delete_session(
        self,
        *,
        session_key: str,
        semantic_set_id: str | None = None,
    ) -> None:
        session = await self._session_store.get_session(session_key)
        if session is None:
            return
        resolved_set_id = semantic_set_id or self._set_id_resolver(session)
        await self._episodic_delete_service.delete_session_episodic_memory(
            session_key=session_key
        )
        await self._cleanup_semantic_set(resolved_set_id)
        await self._episode_store.purge_session_episodes(session_key)
        await self._session_store.delete_session(session_key)

    async def delete_project(
        self,
        *,
        org_id: str,
        project_id: str,
    ) -> None:
        sessions = await self._session_store.search_sessions(
            org_id=org_id,
            project_id=project_id,
        )
        for session in sessions:
            await self.delete_session(
                session_key=session.session_key,
                semantic_set_id=self._set_id_resolver(session),
            )
        await self._project_store.delete_project(org_id, project_id)

    async def _cleanup_semantic_history(
        self,
        *,
        semantic_set_id: str | None,
        history_ids: list[str],
    ) -> None:
        feature_ids = await self._semantic_feature_store.get_feature_ids_by_history_ids(
            history_ids
        )
        await self._semantic_feature_store.delete_history(history_ids)
        orphan_feature_ids = await self._semantic_feature_store.get_orphan_feature_ids(
            feature_ids
        )
        await self._semantic_feature_store.delete_features(orphan_feature_ids)
        if semantic_set_id is not None:
            remaining_history = await self._semantic_feature_store.get_history_messages(
                set_ids=[semantic_set_id],
                is_ingested=None,
            )
            if not remaining_history:
                return

    async def _cleanup_semantic_set(self, set_id: str) -> None:
        history_ids = await self._semantic_feature_store.get_history_messages(
            set_ids=[set_id],
            is_ingested=None,
        )
        if history_ids:
            await self._cleanup_semantic_history(
                semantic_set_id=set_id,
                history_ids=history_ids,
            )
        await self._semantic_service.semantic_delete(set_id=set_id)

    async def _build_short_term_context(self, session_key: str) -> str:
        session = await self._session_store.get_session(session_key)
        if session is None:
            return ""
        short_term = await ShortTermMemory.create(
            session_key=session_key,
            session_store=self._session_store,
            message_capacity=self._short_term_capacity,
        )
        recent_episodes = await self._episode_store.list_episodes(
            session_key=session_key,
            include_deleted=False,
            limit=5,
        )
        if recent_episodes:
            restored = ShortTermMemory(
                session_key=session_key,
                session_store=self._session_store,
                message_capacity=self._short_term_capacity,
                summary=short_term.summary,
                messages=[
                    ShortTermMessage(
                        uid=episode.uid,
                        content=episode.content,
                        producer_id=episode.producer_id,
                        producer_role=episode.producer_role,
                        created_at=episode.created_at,
                    )
                    for episode in recent_episodes
                ],
            )
            return restored.get_context()
        return short_term.get_context()

    async def _search_episodic_queries(
        self,
        *,
        subqueries: list[str],
        session_id: str | None,
        producer_role: str | None,
        episode_type: str | None,
        limit: int,
        context_window: int,
        min_score: float,
    ) -> EpisodicSearchResult:
        merged_matches = []
        merged_context: dict[str, EpisodeRecord] = {}
        for subquery in subqueries:
            result = await self._episodic_search_service.search(
                query=subquery,
                session_id=session_id,
                producer_role=producer_role,
                episode_type=episode_type,
                limit=limit,
                context_window=context_window,
                min_score=min_score,
            )
            merged_matches.extend(result.matches)
            for episode in result.expanded_context:
                merged_context[episode.uid] = episode
        deduped_matches = self._dedupe_matches(merged_matches)[:limit]
        return EpisodicSearchResult(
            matches=deduped_matches,
            expanded_context=sorted(
                merged_context.values(),
                key=lambda episode: (episode.sequence_num, episode.created_at, episode.uid),
            ),
        )

    async def _search_semantic_queries(
        self,
        *,
        subqueries: list[str],
        semantic_set_id: str | None,
        limit: int,
    ) -> SemanticSearchResult:
        merged_features = []
        seen_feature_ids: set[int] = set()
        for subquery in subqueries:
            result = await self._semantic_service.semantic_search(
                query=subquery,
                set_id=semantic_set_id,
                limit=limit,
            )
            for feature in result.features:
                if feature.id in seen_feature_ids:
                    continue
                seen_feature_ids.add(feature.id)
                merged_features.append(feature)
        return SemanticSearchResult(features=merged_features[:limit])

    def _dedupe_matches(self, matches):
        best_by_uid = {}
        for match in matches:
            current = best_by_uid.get(match.episode.uid)
            if current is None or match.score > current.score:
                best_by_uid[match.episode.uid] = match
        return sorted(
            best_by_uid.values(),
            key=lambda match: (
                -match.score,
                match.episode.sequence_num,
                match.episode.created_at,
                match.episode.uid,
            ),
        )

    def _merge_results(
        self,
        *,
        episodic_result: EpisodicSearchResult | None,
        semantic_result: SemanticSearchResult | None,
    ) -> list[CombinedMemoryItem]:
        merged: list[CombinedMemoryItem] = []
        if episodic_result is not None:
            merged.extend(
                CombinedMemoryItem(
                    source="episodic",
                    content=match.episode.content,
                    identifier=match.episode.uid,
                    score=match.score,
                )
                for match in episodic_result.matches
            )
        if semantic_result is not None:
            semantic_count = len(semantic_result.features)
            merged.extend(
                CombinedMemoryItem(
                    source="semantic",
                    content=feature.value,
                    identifier=str(feature.id),
                    score=1.0 - (index / max(semantic_count, 1)),
                )
                for index, feature in enumerate(semantic_result.features)
            )
        return sorted(
            merged,
            key=lambda item: (-item.score, item.source, item.identifier),
        )

    def _resolve_mode(
        self,
        *,
        requested_mode: SearchMode,
        session_id: str | None,
        semantic_set_id: str | None,
    ) -> SearchMode:
        if requested_mode != "auto":
            return requested_mode
        if session_id is not None and semantic_set_id is not None:
            return "mixed"
        if session_id is not None:
            return "episodic"
        if semantic_set_id is not None:
            return "semantic"
        return "mixed"
