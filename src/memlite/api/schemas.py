"""Pydantic schemas for REST API."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    org_id: str
    project_id: str
    description: str | None = None


class ProjectResponse(BaseModel):
    org_id: str
    project_id: str
    description: str | None
    created_at: str
    updated_at: str


class SessionCreateRequest(BaseModel):
    session_key: str
    org_id: str
    project_id: str
    session_id: str
    user_id: str | None = None
    agent_id: str | None = None
    group_id: str | None = None


class EpisodeInput(BaseModel):
    uid: str
    session_key: str
    session_id: str
    producer_id: str
    producer_role: str
    produced_for_id: str | None = None
    sequence_num: int = 0
    content: str
    content_type: str = "text"
    episode_type: str = "message"
    metadata_json: str | None = None
    filterable_metadata_json: str | None = None


class MemoryAddRequest(BaseModel):
    session_key: str
    semantic_set_id: str | None = None
    episodes: list[EpisodeInput]


class EpisodeResponse(BaseModel):
    uid: str
    session_key: str
    session_id: str
    producer_id: str
    producer_role: str
    produced_for_id: str | None
    sequence_num: int
    content: str
    content_type: str
    episode_type: str
    created_at: str
    metadata_json: str | None
    filterable_metadata_json: str | None
    deleted: int


class MemorySearchRequest(BaseModel):
    query: str
    session_key: str | None = None
    session_id: str | None = None
    semantic_set_id: str | None = None
    mode: Literal["auto", "episodic", "semantic", "mixed"] = "auto"
    limit: int = 5
    context_window: int = 1
    min_score: float = 0.0001
    producer_role: str | None = None
    episode_type: str | None = None


class CombinedMemoryItemResponse(BaseModel):
    source: Literal["episodic", "semantic"]
    content: str
    identifier: str
    score: float


class EpisodicMatchResponse(BaseModel):
    episode: EpisodeResponse
    derivative_uid: str
    score: float


class SemanticFeatureResponse(BaseModel):
    id: int
    set_id: str
    category: str
    tag: str
    feature_name: str
    value: str
    metadata_json: str | None
    created_at: str
    updated_at: str
    deleted: int


class MemorySearchResponse(BaseModel):
    mode: str
    rewritten_query: str
    subqueries: list[str]
    episodic_matches: list[EpisodicMatchResponse] = Field(default_factory=list)
    semantic_features: list[SemanticFeatureResponse] = Field(default_factory=list)
    combined: list[CombinedMemoryItemResponse] = Field(default_factory=list)
    expanded_context: list[EpisodeResponse] = Field(default_factory=list)
    short_term_context: str = ""


class EpisodicDeleteRequest(BaseModel):
    episode_uids: list[str] = Field(default_factory=list)
    semantic_set_id: str | None = None


class SemanticDeleteRequest(BaseModel):
    feature_ids: list[int] | None = None
    set_id: str | None = None
    category: str | None = None
    tag: str | None = None


class SemanticFeatureCreateRequest(BaseModel):
    set_id: str
    category: str
    tag: str
    feature_name: str
    value: str
    metadata_json: str | None = None
    embedding: list[float] | None = None


class SemanticFeatureUpdateRequest(BaseModel):
    set_id: str | None = None
    category: str | None = None
    tag: str | None = None
    feature_name: str | None = None
    value: str | None = None
    metadata_json: str | None = None
    embedding: list[float] | None = None


class AgentModeRequest(BaseModel):
    query: str
    session_key: str | None = None
    session_id: str | None = None
    semantic_set_id: str | None = None
    mode: Literal["auto", "episodic", "semantic", "mixed"] = "auto"
    limit: int = 5
    context_window: int = 1


class AgentModeResponse(BaseModel):
    search: MemorySearchResponse
    context_text: str


def to_project_response(project) -> ProjectResponse:
    return ProjectResponse.model_validate(project, from_attributes=True)


def to_episode_response(episode) -> EpisodeResponse:
    return EpisodeResponse.model_validate(episode, from_attributes=True)


def to_feature_response(feature) -> SemanticFeatureResponse:
    return SemanticFeatureResponse.model_validate(feature, from_attributes=True)


def dump_episode_payload(episode: EpisodeInput) -> dict[str, Any]:
    return episode.model_dump()
