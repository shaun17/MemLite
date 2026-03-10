"""Configuration API bindings for the MemLite Python SDK."""

from __future__ import annotations

from memolite.api.schemas import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryTemplateCreateRequest,
    CategoryTemplateResponse,
    DisableCategoryRequest,
    EpisodicMemoryConfigResponse,
    EpisodicMemoryConfigUpdateRequest,
    LongTermMemoryConfigResponse,
    LongTermMemoryConfigUpdateRequest,
    SetConfigRequest,
    SetConfigResponse,
    SetTypeCreateRequest,
    SetTypeResponse,
    ShortTermMemoryConfigResponse,
    ShortTermMemoryConfigUpdateRequest,
    TagCreateRequest,
    TagResponse,
)


class MemLiteConfigAPI:
    """Semantic and memory configuration operations."""

    def __init__(self, client) -> None:
        self._client = client

    async def create_set_type(
        self,
        *,
        org_id: str,
        metadata_tags_sig: str,
        org_level_set: bool = False,
        name: str | None = None,
        description: str | None = None,
    ) -> int:
        payload = SetTypeCreateRequest(
            org_id=org_id,
            metadata_tags_sig=metadata_tags_sig,
            org_level_set=org_level_set,
            name=name,
            description=description,
        )
        data = await self._client.request(
            "POST",
            "/semantic/config/set-types",
            json=payload.model_dump(),
        )
        return int(data["id"])

    async def list_set_types(self, *, org_id: str | None = None) -> list[SetTypeResponse]:
        params = {"org_id": org_id} if org_id is not None else None
        data = await self._client.request(
            "GET",
            "/semantic/config/set-types",
            params=params,
        )
        return [SetTypeResponse.model_validate(item) for item in data]

    async def configure_set(
        self,
        *,
        set_id: str,
        set_type_id: int | None = None,
        set_name: str | None = None,
        set_description: str | None = None,
        embedder_name: str | None = None,
        language_model_name: str | None = None,
    ) -> SetConfigResponse:
        payload = SetConfigRequest(
            set_id=set_id,
            set_type_id=set_type_id,
            set_name=set_name,
            set_description=set_description,
            embedder_name=embedder_name,
            language_model_name=language_model_name,
        )
        data = await self._client.request(
            "POST",
            "/semantic/config/sets",
            json=payload.model_dump(),
        )
        return SetConfigResponse.model_validate(data)

    async def get_set_config(self, *, set_id: str) -> SetConfigResponse:
        data = await self._client.request("GET", f"/semantic/config/sets/{set_id}")
        return SetConfigResponse.model_validate(data)

    async def list_set_ids(self) -> list[str]:
        data = await self._client.request("GET", "/semantic/config/sets")
        return [str(item) for item in data]

    async def add_category(
        self,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        set_id: str | None = None,
        set_type_id: int | None = None,
    ) -> int:
        payload = CategoryCreateRequest(
            name=name,
            prompt=prompt,
            description=description,
            set_id=set_id,
            set_type_id=set_type_id,
        )
        data = await self._client.request(
            "POST",
            "/semantic/config/categories",
            json=payload.model_dump(),
        )
        return int(data["id"])

    async def list_categories(self, *, set_id: str) -> list[CategoryResponse]:
        data = await self._client.request(
            "GET",
            "/semantic/config/categories",
            params={"set_id": set_id},
        )
        return [CategoryResponse.model_validate(item) for item in data]

    async def add_category_template(
        self,
        *,
        name: str,
        category_name: str,
        prompt: str,
        description: str | None = None,
        set_type_id: int | None = None,
    ) -> int:
        payload = CategoryTemplateCreateRequest(
            name=name,
            category_name=category_name,
            prompt=prompt,
            description=description,
            set_type_id=set_type_id,
        )
        data = await self._client.request(
            "POST",
            "/semantic/config/category-templates",
            json=payload.model_dump(),
        )
        return int(data["id"])

    async def list_category_templates(
        self,
        *,
        set_type_id: int | None = None,
    ) -> list[CategoryTemplateResponse]:
        params = {"set_type_id": set_type_id} if set_type_id is not None else None
        data = await self._client.request(
            "GET",
            "/semantic/config/category-templates",
            params=params,
        )
        return [CategoryTemplateResponse.model_validate(item) for item in data]

    async def disable_category(self, *, set_id: str, category_name: str) -> None:
        payload = DisableCategoryRequest(set_id=set_id, category_name=category_name)
        await self._client.request(
            "POST",
            "/semantic/config/disabled-categories",
            json=payload.model_dump(),
        )

    async def add_tag(self, *, category_id: int, name: str, description: str) -> int:
        payload = TagCreateRequest(
            category_id=category_id,
            name=name,
            description=description,
        )
        data = await self._client.request(
            "POST",
            "/semantic/config/tags",
            json=payload.model_dump(),
        )
        return int(data["id"])

    async def list_tags(self, *, category_id: int) -> list[TagResponse]:
        data = await self._client.request(
            "GET",
            "/semantic/config/tags",
            params={"category_id": category_id},
        )
        return [TagResponse.model_validate(item) for item in data]

    async def get_episodic_memory_config(self) -> EpisodicMemoryConfigResponse:
        data = await self._client.request("GET", "/memory-config/episodic")
        return EpisodicMemoryConfigResponse.model_validate(data)

    async def update_episodic_memory_config(
        self,
        *,
        top_k: int | None = None,
        min_score: float | None = None,
        context_window: int | None = None,
        rerank_enabled: bool | None = None,
    ) -> EpisodicMemoryConfigResponse:
        payload = EpisodicMemoryConfigUpdateRequest(
            top_k=top_k,
            min_score=min_score,
            context_window=context_window,
            rerank_enabled=rerank_enabled,
        )
        data = await self._client.request(
            "PATCH",
            "/memory-config/episodic",
            json=payload.model_dump(),
        )
        return EpisodicMemoryConfigResponse.model_validate(data)

    async def get_short_term_memory_config(self) -> ShortTermMemoryConfigResponse:
        data = await self._client.request("GET", "/memory-config/short-term")
        return ShortTermMemoryConfigResponse.model_validate(data)

    async def update_short_term_memory_config(
        self,
        *,
        message_capacity: int | None = None,
        summary_enabled: bool | None = None,
    ) -> ShortTermMemoryConfigResponse:
        payload = ShortTermMemoryConfigUpdateRequest(
            message_capacity=message_capacity,
            summary_enabled=summary_enabled,
        )
        data = await self._client.request(
            "PATCH",
            "/memory-config/short-term",
            json=payload.model_dump(),
        )
        return ShortTermMemoryConfigResponse.model_validate(data)

    async def get_long_term_memory_config(self) -> LongTermMemoryConfigResponse:
        data = await self._client.request("GET", "/memory-config/long-term")
        return LongTermMemoryConfigResponse.model_validate(data)

    async def update_long_term_memory_config(
        self,
        *,
        semantic_enabled: bool | None = None,
        episodic_enabled: bool | None = None,
    ) -> LongTermMemoryConfigResponse:
        payload = LongTermMemoryConfigUpdateRequest(
            semantic_enabled=semantic_enabled,
            episodic_enabled=episodic_enabled,
        )
        data = await self._client.request(
            "PATCH",
            "/memory-config/long-term",
            json=payload.model_dump(),
        )
        return LongTermMemoryConfigResponse.model_validate(data)
