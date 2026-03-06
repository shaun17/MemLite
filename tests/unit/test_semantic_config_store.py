from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.semantic_config_store import SqliteSemanticConfigStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_semantic_config_store_crud(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memlite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSemanticConfigStore(factory)

    set_type_id = await store.create_set_type(
        org_id="org-a",
        metadata_tags_sig="user_id|agent_id",
        name="default",
        description="default set type",
    )
    await store.set_setid_config(
        set_id="set-a",
        set_name="Set A",
        embedder_name="embedder-1",
        language_model_name="llm-1",
    )
    await store.register_set_id_set_type(set_id="set-a", set_type_id=set_type_id)

    inherited_category_id = await store.create_category(
        set_type_id=set_type_id,
        name="profile",
        prompt="profile prompt",
    )
    local_category_id = await store.create_category(
        set_id="set-a",
        name="preferences",
        prompt="preferences prompt",
        description="local category",
    )
    tag_id = await store.create_tag(
        category_id=local_category_id,
        name="food",
        description="Food preference",
    )
    template_id = await store.create_category_template(
        set_type_id=set_type_id,
        name="profile-template",
        category_name="profile",
        prompt="template prompt",
        description="template description",
    )
    await store.add_disabled_category_to_setid(set_id="set-a", category_name="profile")

    set_types = await store.list_set_types("org-a")
    config = await store.get_setid_config("set-a")
    categories = await store.list_categories_for_set("set-a")
    tags = await store.list_tags(local_category_id)
    templates = await store.list_category_templates(set_type_id=set_type_id)
    disabled = await store.get_disabled_categories("set-a")
    category = await store.get_category(local_category_id)

    assert len(set_types) == 1
    assert config is not None and config.embedder_name == "embedder-1"
    assert [entry.name for entry in categories] == ["preferences", "profile"]
    assert categories[1].inherited is True
    assert [entry.name for entry in tags] == ["food"]
    assert [entry.name for entry in templates] == ["profile-template"]
    assert disabled == ["profile"]
    assert category is not None and category.description == "local category"

    await store.delete_tag(tag_id)
    await store.delete_category_template(template_id)
    await store.remove_disabled_category_from_setid(set_id="set-a", category_name="profile")
    await store.delete_category(local_category_id)
    await store.delete_category(inherited_category_id)
    await store.delete_set_type(set_type_id)

    assert await store.list_set_types("org-a") == []

    await factory.dispose()
