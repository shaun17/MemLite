from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.semantic.session_manager import SetBindingRequest, SemanticSessionManager
from memlite.storage.semantic_config_store import SqliteSemanticConfigStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_semantic_session_manager_reload_preserves_binding_and_templates(
    tmp_path: Path,
):
    sqlite_path = tmp_path / "memlite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()
    manager = SemanticSessionManager(SqliteSemanticConfigStore(factory))

    set_type_id = await manager.create_set_type(
        org_id="org-a",
        metadata_tags_sig="user",
        name="org-default",
    )
    await manager.bind_set(
        SetBindingRequest(
            set_id="set-a",
            set_type_id=set_type_id,
            set_name="Set A",
            embedder_name="embedder-1",
        )
    )
    await manager.create_category(
        set_type_id=set_type_id,
        name="persona",
        prompt="persona prompt",
    )
    await manager.create_category_template(
        set_type_id=set_type_id,
        name="persona-template",
        category_name="persona",
        prompt="template prompt",
    )
    await factory.dispose()

    reloaded_factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    reloaded_manager = SemanticSessionManager(SqliteSemanticConfigStore(reloaded_factory))
    config = await reloaded_manager.get_set_config("set-a")
    categories = await reloaded_manager.list_categories("set-a")
    templates = await reloaded_manager.list_category_templates(set_type_id=set_type_id)

    assert config is not None
    assert config.set_name == "Set A"
    assert [entry.name for entry in categories] == ["persona"]
    assert categories[0].inherited is True
    assert [entry.name for entry in templates] == ["persona-template"]

    await reloaded_factory.dispose()
