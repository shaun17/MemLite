"""Semantic session configuration management for MemLite."""

from dataclasses import dataclass

from memolite.storage.semantic_config_store import (
    CategoryRecord,
    CategoryTemplateRecord,
    SetConfigRecord,
    SetTypeRecord,
    SqliteSemanticConfigStore,
    TagRecord,
)


@dataclass(slots=True)
class SetBindingRequest:
    """Binding payload for attaching semantic config to a set id."""

    set_id: str
    set_type_id: int | None = None
    set_name: str | None = None
    set_description: str | None = None
    embedder_name: str | None = None
    language_model_name: str | None = None


class SemanticSessionManager:
    """Manage semantic configuration for a logical memory set."""

    def __init__(self, config_store: SqliteSemanticConfigStore) -> None:
        self._config_store = config_store

    async def create_set_type(
        self,
        *,
        org_id: str,
        metadata_tags_sig: str,
        org_level_set: bool = False,
        name: str | None = None,
        description: str | None = None,
    ) -> int:
        return await self._config_store.create_set_type(
            org_id=org_id,
            metadata_tags_sig=metadata_tags_sig,
            org_level_set=org_level_set,
            name=name,
            description=description,
        )

    async def list_set_types(self, org_id: str | None = None) -> list[SetTypeRecord]:
        return await self._config_store.list_set_types(org_id)

    async def delete_set_type(self, set_type_id: int) -> None:
        await self._config_store.delete_set_type(set_type_id)

    async def list_set_ids(self) -> list[str]:
        return await self._config_store.list_set_ids()

    async def bind_set(self, request: SetBindingRequest) -> SetConfigRecord | None:
        await self._config_store.set_setid_config(
            set_id=request.set_id,
            set_name=request.set_name,
            set_description=request.set_description,
            embedder_name=request.embedder_name,
            language_model_name=request.language_model_name,
        )
        if request.set_type_id is not None:
            await self._config_store.register_set_id_set_type(
                set_id=request.set_id,
                set_type_id=request.set_type_id,
            )
        return await self._config_store.get_setid_config(request.set_id)

    async def get_set_config(self, set_id: str) -> SetConfigRecord | None:
        return await self._config_store.get_setid_config(set_id)

    async def create_category(
        self,
        *,
        name: str,
        prompt: str,
        description: str | None = None,
        set_id: str | None = None,
        set_type_id: int | None = None,
    ) -> int:
        return await self._config_store.create_category(
            name=name,
            prompt=prompt,
            description=description,
            set_id=set_id,
            set_type_id=set_type_id,
        )

    async def get_category(self, category_id: int) -> CategoryRecord | None:
        return await self._config_store.get_category(category_id)

    async def list_categories(self, set_id: str) -> list[CategoryRecord]:
        return await self._config_store.list_categories_for_set(set_id)

    async def get_category_set_ids(self, name: str) -> list[str]:
        return await self._config_store.get_category_set_ids(name)

    async def delete_category(self, category_id: int) -> None:
        await self._config_store.delete_category(category_id)

    async def create_category_template(
        self,
        *,
        name: str,
        category_name: str,
        prompt: str,
        description: str | None = None,
        set_type_id: int | None = None,
    ) -> int:
        return await self._config_store.create_category_template(
            name=name,
            category_name=category_name,
            prompt=prompt,
            description=description,
            set_type_id=set_type_id,
        )

    async def list_category_templates(
        self,
        *,
        set_type_id: int | None = None,
    ) -> list[CategoryTemplateRecord]:
        return await self._config_store.list_category_templates(set_type_id=set_type_id)

    async def delete_category_template(self, template_id: int) -> None:
        await self._config_store.delete_category_template(template_id)

    async def create_tag(
        self,
        *,
        category_id: int,
        name: str,
        description: str,
    ) -> int:
        return await self._config_store.create_tag(
            category_id=category_id,
            name=name,
            description=description,
        )

    async def list_tags(self, category_id: int) -> list[TagRecord]:
        return await self._config_store.list_tags(category_id)

    async def delete_tag(self, tag_id: int) -> None:
        await self._config_store.delete_tag(tag_id)

    async def disable_category(self, *, set_id: str, category_name: str) -> None:
        await self._config_store.add_disabled_category_to_setid(
            set_id=set_id,
            category_name=category_name,
        )

    async def enable_category(self, *, set_id: str, category_name: str) -> None:
        await self._config_store.remove_disabled_category_from_setid(
            set_id=set_id,
            category_name=category_name,
        )

    async def list_disabled_categories(self, set_id: str) -> list[str]:
        return await self._config_store.get_disabled_categories(set_id)
