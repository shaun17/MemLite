from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.storage.semantic_config_store import SqliteSemanticConfigStore
from memolite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_semantic_config_store_reload_keeps_inherited_categories(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()
    store = SqliteSemanticConfigStore(factory)

    set_type_id = await store.create_set_type(
        org_id="org-a",
        metadata_tags_sig="user",
        name="org-default",
    )
    await store.register_set_id_set_type(set_id="set-a", set_type_id=set_type_id)
    await store.create_category(
        set_type_id=set_type_id,
        name="persona",
        prompt="persona prompt",
    )
    await factory.dispose()

    reloaded_factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    reloaded_store = SqliteSemanticConfigStore(reloaded_factory)
    categories = await reloaded_store.list_categories_for_set("set-a")

    assert [entry.name for entry in categories] == ["persona"]
    assert categories[0].inherited is True

    await reloaded_factory.dispose()
