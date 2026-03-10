"""Episodic delete and cleanup services."""

from __future__ import annotations

from dataclasses import dataclass

from memolite.episodic.derivative_pipeline import vector_item_id
from memolite.storage.episode_store import EpisodeRecord, SqliteEpisodeStore
from memolite.storage.graph_store import KuzuGraphStore
from memolite.storage.sqlite_vec import SqliteVecIndex


@dataclass(slots=True)
class EpisodicDeleteSummary:
    """Summary of deleted episodic data."""

    episode_uids: list[str]
    derivative_uids: list[str]


class EpisodicDeleteService:
    """Delete episodes and clean related derivative graph/vector state."""

    def __init__(
        self,
        *,
        episode_store: SqliteEpisodeStore,
        graph_store: KuzuGraphStore,
        derivative_index: SqliteVecIndex,
    ) -> None:
        self._episode_store = episode_store
        self._graph_store = graph_store
        self._derivative_index = derivative_index

    async def delete_episode_uids(self, episode_uids: list[str]) -> EpisodicDeleteSummary:
        if not episode_uids:
            return EpisodicDeleteSummary(episode_uids=[], derivative_uids=[])

        derivative_uids = await self._collect_derivative_uids(episode_uids)
        await self._episode_store.delete_episodes(episode_uids)
        await self._cleanup_derivatives(derivative_uids)
        await self._graph_store.delete_nodes(node_table="Episode", uids=episode_uids)
        return EpisodicDeleteSummary(
            episode_uids=episode_uids,
            derivative_uids=derivative_uids,
        )

    async def delete_matching_episodes(
        self,
        *,
        session_key: str | None = None,
        producer_role: str | None = None,
        episode_type: str | None = None,
    ) -> EpisodicDeleteSummary:
        episodes = await self._episode_store.find_matching_episodes(
            session_key=session_key,
            producer_role=producer_role,
            episode_type=episode_type,
            include_deleted=False,
        )
        return await self.delete_episode_uids([episode.uid for episode in episodes])

    async def delete_session_episodic_memory(
        self,
        *,
        session_key: str,
    ) -> EpisodicDeleteSummary:
        episodes = await self._episode_store.list_episodes(
            session_key=session_key,
            include_deleted=False,
        )
        await self._episode_store.delete_session_episodes(session_key)
        episode_uids = [episode.uid for episode in episodes]
        derivative_uids = await self._collect_derivative_uids(episode_uids)
        await self._cleanup_derivatives(derivative_uids)
        await self._graph_store.delete_nodes(node_table="Episode", uids=episode_uids)
        return EpisodicDeleteSummary(
            episode_uids=episode_uids,
            derivative_uids=derivative_uids,
        )

    async def _collect_derivative_uids(self, episode_uids: list[str]) -> list[str]:
        derivative_uids: list[str] = []
        for episode_uid in episode_uids:
            derivatives = await self._graph_store.search_directional_nodes(
                source_table="Episode",
                source_uid=episode_uid,
                relation_table="DERIVED_FROM",
                target_table="Derivative",
                direction="in",
            )
            derivative_uids.extend(str(node.properties["uid"]) for node in derivatives)
        return sorted(set(derivative_uids))

    async def _cleanup_derivatives(self, derivative_uids: list[str]) -> None:
        if not derivative_uids:
            return
        await self._derivative_index.delete_many(
            [vector_item_id(derivative_uid) for derivative_uid in derivative_uids]
        )
        await self._graph_store.delete_nodes(
            node_table="Derivative",
            uids=derivative_uids,
        )
