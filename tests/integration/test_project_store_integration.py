from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.project_store import SqliteProjectStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_project_store_supports_cross_operation_flow(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteProjectStore(factory)

    await store.create_project("org-1", "proj-1", description="First")
    await store.create_project("org-2", "proj-2", description="Second")

    all_projects = await store.list_projects()
    org_1_project = await store.get_project("org-1", "proj-1")

    assert len(all_projects) == 2
    assert org_1_project is not None
    assert org_1_project.project_id == "proj-1"

    await factory.dispose()
