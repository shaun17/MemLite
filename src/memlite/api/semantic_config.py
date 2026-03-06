"""Semantic set/config/category/tag API routes."""

from fastapi import APIRouter, Depends, HTTPException

from memlite.api.deps import get_resources
from memlite.api.schemas import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryTemplateCreateRequest,
    CategoryTemplateResponse,
    DisableCategoryRequest,
    SetConfigRequest,
    SetConfigResponse,
    SetTypeCreateRequest,
    SetTypeResponse,
    TagCreateRequest,
    TagResponse,
    to_category_response,
    to_category_template_response,
    to_set_config_response,
    to_set_type_response,
    to_tag_response,
)
from memlite.app.resources import ResourceManager
from memlite.semantic.session_manager import SetBindingRequest

router = APIRouter(prefix="/semantic/config", tags=["semantic-config"])


@router.post("/set-types", response_model=dict[str, int])
async def create_set_type(
    payload: SetTypeCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, int]:
    identifier = await resources.semantic_session_manager.create_set_type(
        org_id=payload.org_id,
        metadata_tags_sig=payload.metadata_tags_sig,
        org_level_set=payload.org_level_set,
        name=payload.name,
        description=payload.description,
    )
    return {"id": identifier}


@router.get("/set-types", response_model=list[SetTypeResponse])
async def list_set_types(
    org_id: str | None = None,
    resources: ResourceManager = Depends(get_resources),
) -> list[SetTypeResponse]:
    records = await resources.semantic_session_manager.list_set_types(org_id)
    return [to_set_type_response(record) for record in records]


@router.delete("/set-types/{set_type_id}", response_model=dict[str, str])
async def delete_set_type(
    set_type_id: int,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.semantic_session_manager.delete_set_type(set_type_id)
    return {"status": "ok"}


@router.post("/sets", response_model=SetConfigResponse)
async def configure_set(
    payload: SetConfigRequest,
    resources: ResourceManager = Depends(get_resources),
) -> SetConfigResponse:
    config = await resources.semantic_session_manager.bind_set(
        SetBindingRequest(**payload.model_dump())
    )
    if config is None:
        raise HTTPException(status_code=500, detail="failed to configure set")
    return to_set_config_response(config)


@router.get("/sets/{set_id}", response_model=SetConfigResponse)
async def get_set_config(
    set_id: str,
    resources: ResourceManager = Depends(get_resources),
) -> SetConfigResponse:
    config = await resources.semantic_session_manager.get_set_config(set_id)
    if config is None:
        raise HTTPException(status_code=404, detail="set config not found")
    return to_set_config_response(config)


@router.get("/sets", response_model=list[str])
async def list_set_ids(
    resources: ResourceManager = Depends(get_resources),
) -> list[str]:
    return await resources.semantic_session_manager.list_set_ids()


@router.post("/categories", response_model=dict[str, int])
async def add_category(
    payload: CategoryCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, int]:
    identifier = await resources.semantic_session_manager.create_category(
        name=payload.name,
        prompt=payload.prompt,
        description=payload.description,
        set_id=payload.set_id,
        set_type_id=payload.set_type_id,
    )
    return {"id": identifier}


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    resources: ResourceManager = Depends(get_resources),
) -> CategoryResponse:
    category = await resources.semantic_session_manager.get_category(category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    return to_category_response(category)


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    set_id: str,
    resources: ResourceManager = Depends(get_resources),
) -> list[CategoryResponse]:
    categories = await resources.semantic_session_manager.list_categories(set_id)
    return [to_category_response(category) for category in categories]


@router.get("/categories/{name}/set-ids", response_model=list[str])
async def get_category_set_ids(
    name: str,
    resources: ResourceManager = Depends(get_resources),
) -> list[str]:
    return await resources.semantic_session_manager.get_category_set_ids(name)


@router.delete("/categories/{category_id}", response_model=dict[str, str])
async def delete_category(
    category_id: int,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.semantic_session_manager.delete_category(category_id)
    return {"status": "ok"}


@router.post("/category-templates", response_model=dict[str, int])
async def add_category_template(
    payload: CategoryTemplateCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, int]:
    identifier = await resources.semantic_session_manager.create_category_template(
        name=payload.name,
        category_name=payload.category_name,
        prompt=payload.prompt,
        description=payload.description,
        set_type_id=payload.set_type_id,
    )
    return {"id": identifier}


@router.get("/category-templates", response_model=list[CategoryTemplateResponse])
async def list_category_templates(
    set_type_id: int | None = None,
    resources: ResourceManager = Depends(get_resources),
) -> list[CategoryTemplateResponse]:
    records = await resources.semantic_session_manager.list_category_templates(
        set_type_id=set_type_id
    )
    return [to_category_template_response(record) for record in records]


@router.post("/disabled-categories", response_model=dict[str, str])
async def disable_category(
    payload: DisableCategoryRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.semantic_session_manager.disable_category(
        set_id=payload.set_id,
        category_name=payload.category_name,
    )
    return {"status": "ok"}


@router.get("/disabled-categories/{set_id}", response_model=list[str])
async def list_disabled_categories(
    set_id: str,
    resources: ResourceManager = Depends(get_resources),
) -> list[str]:
    return await resources.semantic_session_manager.list_disabled_categories(set_id)


@router.post("/tags", response_model=dict[str, int])
async def add_tag(
    payload: TagCreateRequest,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, int]:
    identifier = await resources.semantic_session_manager.create_tag(
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
    )
    return {"id": identifier}


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(
    category_id: int,
    resources: ResourceManager = Depends(get_resources),
) -> list[TagResponse]:
    records = await resources.semantic_session_manager.list_tags(category_id)
    return [to_tag_response(record) for record in records]


@router.delete("/tags/{tag_id}", response_model=dict[str, str])
async def delete_tag(
    tag_id: int,
    resources: ResourceManager = Depends(get_resources),
) -> dict[str, str]:
    await resources.semantic_session_manager.delete_tag(tag_id)
    return {"status": "ok"}
