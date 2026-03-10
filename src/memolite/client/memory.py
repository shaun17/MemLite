"""Memory API bindings for the MemLite Python SDK."""

from __future__ import annotations

from typing import Literal

from memolite.api.schemas import (
    AgentModeRequest,
    AgentModeResponse,
    EpisodeInput,
    EpisodeResponse,
    EpisodicDeleteRequest,
    MemoryAddRequest,
    MemorySearchRequest,
    MemorySearchResponse,
    SemanticDeleteRequest,
)


class MemLiteMemoryAPI:
    """Memory operations."""

    def __init__(self, client) -> None:
        self._client = client

    async def add(
        self,
        *,
        session_key: str,
        episodes: list[EpisodeInput | dict],
        semantic_set_id: str | None = None,
    ) -> list[str]:
        payload = MemoryAddRequest(
            session_key=session_key,
            semantic_set_id=semantic_set_id,
            episodes=[
                episode
                if isinstance(episode, EpisodeInput)
                else EpisodeInput.model_validate(episode)
                for episode in episodes
            ],
        )
        data = await self._client.request("POST", "/memories", json=payload.model_dump())
        return [item["uid"] for item in data]

    async def search(
        self,
        *,
        query: str,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: Literal["auto", "episodic", "semantic", "mixed"] = "auto",
        limit: int = 5,
        context_window: int = 1,
        min_score: float = 0.0001,
        producer_role: str | None = None,
        episode_type: str | None = None,
    ) -> MemorySearchResponse:
        payload = MemorySearchRequest(
            query=query,
            session_key=session_key,
            session_id=session_id,
            semantic_set_id=semantic_set_id,
            mode=mode,
            limit=limit,
            context_window=context_window,
            min_score=min_score,
            producer_role=producer_role,
            episode_type=episode_type,
        )
        data = await self._client.request(
            "POST",
            "/memories/search",
            json=payload.model_dump(),
        )
        return MemorySearchResponse.model_validate(data)

    async def agent(
        self,
        *,
        query: str,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: Literal["auto", "episodic", "semantic", "mixed"] = "auto",
        limit: int = 5,
        context_window: int = 1,
    ) -> AgentModeResponse:
        payload = AgentModeRequest(
            query=query,
            session_key=session_key,
            session_id=session_id,
            semantic_set_id=semantic_set_id,
            mode=mode,
            limit=limit,
            context_window=context_window,
        )
        data = await self._client.request("POST", "/memories/agent", json=payload.model_dump())
        return AgentModeResponse.model_validate(data)

    async def list(self, *, session_key: str) -> list[EpisodeResponse]:
        data = await self._client.request(
            "GET",
            "/memories",
            params={"session_key": session_key},
        )
        return [EpisodeResponse.model_validate(item) for item in data]

    async def delete_episodes(
        self,
        *,
        episode_uids: list[str],
        semantic_set_id: str | None = None,
    ) -> None:
        payload = EpisodicDeleteRequest(
            episode_uids=episode_uids,
            semantic_set_id=semantic_set_id,
        )
        await self._client.request(
            "DELETE",
            "/memories/episodes",
            json=payload.model_dump(),
        )

    async def delete_semantic(
        self,
        *,
        feature_ids: list[int] | None = None,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> None:
        payload = SemanticDeleteRequest(
            feature_ids=feature_ids,
            set_id=set_id,
            category=category,
            tag=tag,
        )
        await self._client.request(
            "DELETE",
            "/memories/semantic",
            json=payload.model_dump(),
        )
