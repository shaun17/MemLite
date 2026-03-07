"""Memory API routes."""

from typing import Literal

from fastapi import APIRouter, Depends

from memlite.api.deps import get_resources
from memlite.api.schemas import (
    AgentModeRequest,
    AgentModeResponse,
    EpisodicDeleteRequest,
    MemoryAddRequest,
    MemorySearchRequest,
    MemorySearchResponse,
    SemanticDeleteRequest,
    dump_episode_payload,
    to_episode_response,
    to_feature_response,
)
from memlite.app.resources import ResourceManager

router = APIRouter(prefix="/memories", tags=["memory"])


def _resolve_mode_with_config(
    *,
    requested: Literal["auto", "episodic", "semantic", "mixed"],
    episodic_enabled: bool,
    semantic_enabled: bool,
) -> Literal["auto", "episodic", "semantic", "mixed"]:
    if requested == "auto":
        if episodic_enabled and semantic_enabled:
            return "auto"
        if episodic_enabled:
            return "episodic"
        if semantic_enabled:
            return "semantic"
        return "episodic"

    if requested == "mixed":
        if episodic_enabled and semantic_enabled:
            return "mixed"
        if episodic_enabled:
            return "episodic"
        if semantic_enabled:
            return "semantic"
        return "episodic"

    if requested == "episodic" and not episodic_enabled:
        return "semantic" if semantic_enabled else "episodic"
    if requested == "semantic" and not semantic_enabled:
        return "episodic" if episodic_enabled else "semantic"
    return requested


@router.post("", response_model=list[dict[str, str]])
async def add_memories(
    payload: MemoryAddRequest,
    resources: ResourceManager = Depends(get_resources),
) -> list[dict[str, str]]:
    episodes = await resources.orchestrator.add_episodes(
        session_key=payload.session_key,
        semantic_set_id=payload.semantic_set_id,
        episodes=[dump_episode_payload(episode) for episode in payload.episodes],
    )
    return [{"uid": episode.uid} for episode in episodes]


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    payload: MemorySearchRequest,
    resources: ResourceManager = Depends(get_resources),
) -> MemorySearchResponse:
    episodic_config = resources.memory_config.get_episodic()
    long_term_config = resources.memory_config.get_long_term()
    resolved_mode = _resolve_mode_with_config(
        requested=payload.mode,
        episodic_enabled=long_term_config.episodic_enabled,
        semantic_enabled=long_term_config.semantic_enabled,
    )
    result = await resources.orchestrator.search_memories(
        query=payload.query,
        session_key=payload.session_key,
        session_id=payload.session_id,
        semantic_set_id=payload.semantic_set_id,
        mode=resolved_mode,
        limit=payload.limit if payload.limit is not None else episodic_config.top_k,
        context_window=(
            payload.context_window
            if payload.context_window is not None
            else episodic_config.context_window
        ),
        min_score=(
            payload.min_score
            if payload.min_score is not None
            else episodic_config.min_score
        ),
        producer_role=payload.producer_role,
        episode_type=payload.episode_type,
    )
    return MemorySearchResponse(
        mode=result.mode,
        rewritten_query=result.rewritten_query,
        subqueries=result.subqueries,
        episodic_matches=[
            {
                "episode": to_episode_response(match.episode),
                "derivative_uid": match.derivative_uid,
                "score": match.score,
            }
            for match in (result.episodic.matches if result.episodic else [])
        ],
        semantic_features=[
            to_feature_response(feature)
            for feature in (result.semantic.features if result.semantic else [])
        ],
        combined=[
            {
                "source": item.source,
                "content": item.content,
                "identifier": item.identifier,
                "score": item.score,
            }
            for item in result.combined
        ],
        expanded_context=[
            to_episode_response(episode)
            for episode in (result.episodic.expanded_context if result.episodic else [])
        ],
        short_term_context=result.short_term_context,
    )


@router.post("/agent", response_model=AgentModeResponse)
async def agent_mode(
    payload: AgentModeRequest,
    resources: ResourceManager = Depends(get_resources),
) -> AgentModeResponse:
    episodic_config = resources.memory_config.get_episodic()
    long_term_config = resources.memory_config.get_long_term()
    resolved_mode = _resolve_mode_with_config(
        requested=payload.mode,
        episodic_enabled=long_term_config.episodic_enabled,
        semantic_enabled=long_term_config.semantic_enabled,
    )
    result = await resources.orchestrator.agent_mode(
        query=payload.query,
        session_key=payload.session_key,
        session_id=payload.session_id,
        semantic_set_id=payload.semantic_set_id,
        mode=resolved_mode,
        limit=payload.limit if payload.limit is not None else episodic_config.top_k,
        context_window=(
            payload.context_window
            if payload.context_window is not None
            else episodic_config.context_window
        ),
    )
    search = MemorySearchResponse(
        mode=result.search.mode,
        rewritten_query=result.search.rewritten_query,
        subqueries=result.search.subqueries,
        episodic_matches=[
            {
                "episode": to_episode_response(match.episode),
                "derivative_uid": match.derivative_uid,
                "score": match.score,
            }
            for match in (result.search.episodic.matches if result.search.episodic else [])
        ],
        semantic_features=[
            to_feature_response(feature)
            for feature in (result.search.semantic.features if result.search.semantic else [])
        ],
        combined=[
            {
                "source": item.source,
                "content": item.content,
                "identifier": item.identifier,
                "score": item.score,
            }
            for item in result.search.combined
        ],
        expanded_context=[
            to_episode_response(episode)
            for episode in (
                result.search.episodic.expanded_context if result.search.episodic else []
            )
        ],
        short_term_context=result.search.short_term_context,
    )
    return AgentModeResponse(search=search, context_text=result.context_text)


@router.get("", response_model=list[dict])
async def list_memories(
    session_key: str,
    resources: ResourceManager = Depends(get_resources),
) -> list[dict]:
    episodes = await resources.episode_store.list_episodes(session_key=session_key)
    return [to_episode_response(episode).model_dump() for episode in episodes]


@router.get("/{uid}", response_model=dict | None)
async def get_memory(
    uid: str,
    resources: ResourceManager = Depends(get_resources),
) -> dict | None:
    episodes = await resources.episode_store.get_episodes([uid])
    if not episodes:
        return None
    return to_episode_response(episodes[0]).model_dump()


@router.delete("/episodes", response_model=dict[str, str])
async def delete_episodic_memories(
    payload: EpisodicDeleteRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.orchestrator.delete_episodes(
        episode_uids=payload.episode_uids,
        semantic_set_id=payload.semantic_set_id,
    )
    return {"status": "ok"}


@router.delete("/semantic", response_model=dict[str, str])
async def delete_semantic_memories(
    payload: SemanticDeleteRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.semantic_service.semantic_delete(
        feature_ids=payload.feature_ids,
        set_id=payload.set_id,
        category=payload.category,
        tag=payload.tag,
    )
    return {"status": "ok"}
