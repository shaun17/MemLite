"""Memory configuration API routes."""

from fastapi import APIRouter, Depends

from memolite.api.deps import get_resources
from memolite.api.schemas import (
    EpisodicMemoryConfigResponse,
    EpisodicMemoryConfigUpdateRequest,
    LongTermMemoryConfigResponse,
    LongTermMemoryConfigUpdateRequest,
    ShortTermMemoryConfigResponse,
    ShortTermMemoryConfigUpdateRequest,
    to_episodic_memory_config_response,
    to_long_term_memory_config_response,
    to_short_term_memory_config_response,
)
from memolite.app.resources import ResourceManager

router = APIRouter(prefix="/memory-config", tags=["memory-config"])


@router.get("/episodic", response_model=EpisodicMemoryConfigResponse)
async def get_episodic_memory_config(
    resources: ResourceManager = Depends(get_resources),
) -> EpisodicMemoryConfigResponse:
    return to_episodic_memory_config_response(resources.memory_config.get_episodic())


@router.patch("/episodic", response_model=EpisodicMemoryConfigResponse)
async def configure_episodic_memory(
    payload: EpisodicMemoryConfigUpdateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> EpisodicMemoryConfigResponse:
    config = resources.memory_config.update_episodic(**payload.model_dump())
    return to_episodic_memory_config_response(config)


@router.get("/short-term", response_model=ShortTermMemoryConfigResponse)
async def get_short_term_memory_config(
    resources: ResourceManager = Depends(get_resources),
) -> ShortTermMemoryConfigResponse:
    return to_short_term_memory_config_response(resources.memory_config.get_short_term())


@router.patch("/short-term", response_model=ShortTermMemoryConfigResponse)
async def configure_short_term_memory(
    payload: ShortTermMemoryConfigUpdateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> ShortTermMemoryConfigResponse:
    config = resources.memory_config.update_short_term(**payload.model_dump())
    return to_short_term_memory_config_response(config)


@router.get("/long-term", response_model=LongTermMemoryConfigResponse)
async def get_long_term_memory_config(
    resources: ResourceManager = Depends(get_resources),
) -> LongTermMemoryConfigResponse:
    return to_long_term_memory_config_response(resources.memory_config.get_long_term())


@router.patch("/long-term", response_model=LongTermMemoryConfigResponse)
async def configure_long_term_memory(
    payload: LongTermMemoryConfigUpdateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> LongTermMemoryConfigResponse:
    config = resources.memory_config.update_long_term(**payload.model_dump())
    return to_long_term_memory_config_response(config)
