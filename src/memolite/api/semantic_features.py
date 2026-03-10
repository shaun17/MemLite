"""Semantic feature API routes."""

from fastapi import APIRouter, Depends, HTTPException

from memolite.api.deps import get_resources
from memolite.api.schemas import (
    SemanticFeatureCreateRequest,
    SemanticFeatureResponse,
    SemanticFeatureUpdateRequest,
    to_feature_response,
)
from memolite.app.resources import ResourceManager

router = APIRouter(prefix="/semantic/features", tags=["semantic"])


@router.post("", response_model=dict[str, int])
async def add_feature(
    payload: SemanticFeatureCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, int]:
    feature_id = await resources.semantic_feature_store.add_feature(
        set_id=payload.set_id,
        category=payload.category,
        tag=payload.tag,
        feature_name=payload.feature_name,
        value=payload.value,
        metadata_json=payload.metadata_json,
        embedding=payload.embedding,
    )
    return {"id": feature_id}


@router.get("/{feature_id}", response_model=SemanticFeatureResponse)
async def get_feature(
    feature_id: int,
    resources: ResourceManager = Depends(get_resources),
) -> SemanticFeatureResponse:
    feature = await resources.semantic_feature_store.get_feature(feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="feature not found")
    return to_feature_response(feature)


@router.patch("/{feature_id}", response_model=dict[str, str])
async def update_feature(
    feature_id: int,
    payload: SemanticFeatureUpdateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.semantic_feature_store.update_feature(
        feature_id,
        set_id=payload.set_id,
        category=payload.category,
        tag=payload.tag,
        feature_name=payload.feature_name,
        value=payload.value,
        metadata_json=payload.metadata_json,
        embedding=payload.embedding,
    )
    return {"status": "ok"}
