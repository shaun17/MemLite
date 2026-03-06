from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.semantic.session_manager import SetBindingRequest, SemanticSessionManager
from memlite.storage.semantic_config_store import SqliteSemanticConfigStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_semantic_session_manager_manages_sets_categories_tags_and_templates(
    tmp_path: Path,
):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memlite.sqlite3"))
    await factory.initialize_schema()
    config_store = SqliteSemanticConfigStore(factory)
    manager = SemanticSessionManager(config_store)

    set_type_id = await manager.create_set_type(
        org_id="org-a",
        metadata_tags_sig="user_id|agent_id",
        name="profile-set",
        description="profile defaults",
    )
    bound_config = await manager.bind_set(
        SetBindingRequest(
            set_id="set-a",
            set_type_id=set_type_id,
            set_name="Set A",
            embedder_name="embedder-1",
            language_model_name="llm-1",
        )
    )
    inherited_category_id = await manager.create_category(
        set_type_id=set_type_id,
        name="profile",
        prompt="profile prompt",
    )
    local_category_id = await manager.create_category(
        set_id="set-a",
        name="travel",
        prompt="travel prompt",
    )
    template_id = await manager.create_category_template(
        set_type_id=set_type_id,
        name="travel-template",
        category_name="travel",
        prompt="template prompt",
    )
    tag_id = await manager.create_tag(
        category_id=local_category_id,
        name="seat",
        description="Seat preference",
    )
    await manager.disable_category(set_id="set-a", category_name="profile")

    set_types = await manager.list_set_types("org-a")
    categories = await manager.list_categories("set-a")
    templates = await manager.list_category_templates(set_type_id=set_type_id)
    tags = await manager.list_tags(local_category_id)
    disabled = await manager.list_disabled_categories("set-a")

    assert bound_config is not None
    assert bound_config.embedder_name == "embedder-1"
    assert [entry.name for entry in set_types] == ["profile-set"]
    assert [entry.name for entry in categories] == ["travel", "profile"]
    assert [entry.name for entry in templates] == ["travel-template"]
    assert [entry.name for entry in tags] == ["seat"]
    assert disabled == ["profile"]

    await manager.enable_category(set_id="set-a", category_name="profile")
    await manager.delete_tag(tag_id)
    await manager.delete_category_template(template_id)
    await manager.delete_category(local_category_id)
    await manager.delete_category(inherited_category_id)
    await manager.delete_set_type(set_type_id)

    assert await manager.list_set_types("org-a") == []

    await factory.dispose()
