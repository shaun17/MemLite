"""Episodic similarity search and context expansion."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from memlite.episodic.derivative_pipeline import vector_item_id
from memlite.storage.episode_store import EpisodeRecord, SqliteEpisodeStore
from memlite.storage.graph_store import GraphNodeRecord, KuzuGraphStore
from memlite.storage.sqlite_vec import SqliteVecIndex

EmbedderFn = Callable[[str], Awaitable[list[float]]]
RerankerFn = Callable[[str, list["EpisodicSearchMatch"]], Awaitable[list["EpisodicSearchMatch"]]]


@dataclass(slots=True)
class EpisodicSearchMatch:
    """Matched episode with supporting derivative evidence."""

    episode: EpisodeRecord
    derivative_uid: str
    score: float


@dataclass(slots=True)
class EpisodicSearchResult:
    """Episodic search output."""

    matches: list[EpisodicSearchMatch]
    expanded_context: list[EpisodeRecord]


class EpisodicSearchService:
    """Search derivative vectors and expand back to surrounding episodes."""

    def __init__(
        self,
        *,
        episode_store: SqliteEpisodeStore,
        graph_store: KuzuGraphStore,
        derivative_index: SqliteVecIndex,
        embedder: EmbedderFn,
        reranker: RerankerFn | None = None,
        metrics=None,
    ) -> None:
        self._episode_store = episode_store
        self._graph_store = graph_store
        self._derivative_index = derivative_index
        self._embedder = embedder
        self._reranker = reranker
        self._metrics = metrics

    async def search(
        self,
        *,
        query: str,
        session_id: str | None = None,
        producer_role: str | None = None,
        episode_type: str | None = None,
        limit: int = 5,
        min_score: float = 0.0001,
        context_window: int = 1,
    ) -> EpisodicSearchResult:
        started = perf_counter()
        query_vector = await self._embedder(query)
        derivative_nodes = await self._graph_store.search_matching_nodes(
            node_table="Derivative",
            match_filters={"session_id": session_id} if session_id else None,
        )
        if not derivative_nodes:
            return EpisodicSearchResult(matches=[], expanded_context=[])

        derivative_by_id = {
            vector_item_id(str(node.properties["uid"])): node for node in derivative_nodes
        }
        vector_hits = await self._derivative_index.search_top_k(
            query_vector,
            limit=max(limit * 4, limit),
        )
        relevant_hits = [
            hit for hit in vector_hits if hit.score >= min_score and hit.item_id in derivative_by_id
        ]
        if not relevant_hits:
            return EpisodicSearchResult(matches=[], expanded_context=[])

        episode_uid_by_derivative_uid = await self._lookup_episode_uids(
            [str(derivative_by_id[hit.item_id].properties["uid"]) for hit in relevant_hits]
        )
        episodes = await self._episode_store.get_episodes(list(episode_uid_by_derivative_uid.values()))
        episodes_by_uid = {episode.uid: episode for episode in episodes}

        matches = self._build_matches(
            relevant_hits=relevant_hits,
            derivative_by_id=derivative_by_id,
            episode_uid_by_derivative_uid=episode_uid_by_derivative_uid,
            episodes_by_uid=episodes_by_uid,
            producer_role=producer_role,
            episode_type=episode_type,
        )
        matches = await self._apply_rerank(query=query, matches=matches)
        matches = matches[:limit]

        expanded_context = await self._expand_context(matches, context_window=context_window)
        if self._metrics is not None:
            self._metrics.increment("episodic_search_total")
            self._metrics.observe_timing(
                "search_latency_ms",
                (perf_counter() - started) * 1000,
            )
        return EpisodicSearchResult(matches=matches, expanded_context=expanded_context)

    def _build_matches(
        self,
        *,
        relevant_hits: list,
        derivative_by_id: dict[int, GraphNodeRecord],
        episode_uid_by_derivative_uid: dict[str, str],
        episodes_by_uid: dict[str, EpisodeRecord],
        producer_role: str | None,
        episode_type: str | None,
    ) -> list[EpisodicSearchMatch]:
        matches: list[EpisodicSearchMatch] = []
        seen_episode_uids: set[str] = set()
        for hit in relevant_hits:
            derivative_uid = str(derivative_by_id[hit.item_id].properties["uid"])
            episode_uid = episode_uid_by_derivative_uid.get(derivative_uid)
            if episode_uid is None or episode_uid in seen_episode_uids:
                continue
            episode = episodes_by_uid.get(episode_uid)
            if episode is None:
                continue
            if producer_role is not None and episode.producer_role != producer_role:
                continue
            if episode_type is not None and episode.episode_type != episode_type:
                continue
            seen_episode_uids.add(episode_uid)
            matches.append(
                EpisodicSearchMatch(
                    episode=episode,
                    derivative_uid=derivative_uid,
                    score=hit.score,
                )
            )
        return sorted(
            matches,
            key=lambda match: (
                -match.score,
                match.episode.sequence_num,
                match.episode.created_at,
                match.episode.uid,
            ),
        )

    async def _apply_rerank(
        self,
        *,
        query: str,
        matches: list[EpisodicSearchMatch],
    ) -> list[EpisodicSearchMatch]:
        if self._reranker is None or not matches:
            return matches
        reranked = await self._reranker(query, matches)
        return reranked

    async def _lookup_episode_uids(
        self,
        derivative_uids: list[str],
    ) -> dict[str, str]:
        episode_uid_by_derivative_uid: dict[str, str] = {}
        for derivative_uid in derivative_uids:
            related = await self._graph_store.search_related_nodes(
                source_table="Derivative",
                source_uid=derivative_uid,
                relation_table="DERIVED_FROM",
                target_table="Episode",
            )
            if not related:
                continue
            episode_uid_by_derivative_uid[derivative_uid] = str(related[0].properties["uid"])
        return episode_uid_by_derivative_uid

    async def _expand_context(
        self,
        matches: list[EpisodicSearchMatch],
        *,
        context_window: int,
    ) -> list[EpisodeRecord]:
        expanded_by_uid: dict[str, EpisodeRecord] = {}
        for match in matches:
            episode = match.episode
            session_episodes = await self._episode_store.list_episodes(
                session_key=episode.session_key,
                include_deleted=False,
            )
            min_sequence = max(episode.sequence_num - context_window, 0)
            max_sequence = episode.sequence_num + context_window
            for candidate in session_episodes:
                if min_sequence <= candidate.sequence_num <= max_sequence:
                    expanded_by_uid[candidate.uid] = candidate
        return sorted(
            expanded_by_uid.values(),
            key=lambda episode: (episode.sequence_num, episode.created_at, episode.uid),
        )
