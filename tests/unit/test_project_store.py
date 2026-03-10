from pathlib import Path

import pytest
from sqlalchemy import text

from memlite.common.config import Settings
from memlite.storage.project_store import SqliteProjectStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_project_store_crud_and_listing(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteProjectStore(factory)

    await store.create_project("org-a", "proj-a", description="Project A")
    await store.create_project("org-a", "proj-b", description="Project B")

    project = await store.get_project("org-a", "proj-a")
    projects = await store.list_projects("org-a")

    assert project is not None
    assert project.description == "Project A"
    assert [entry.project_id for entry in projects] == ["proj-a", "proj-b"]

    await store.delete_project("org-a", "proj-b")
    projects_after_delete = await store.list_projects("org-a")

    assert [entry.project_id for entry in projects_after_delete] == ["proj-a"]

    await factory.dispose()


@pytest.mark.anyio
async def test_project_store_episode_count(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteProjectStore(factory)
    await store.create_project("org-a", "proj-a")

    engine = factory.create_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO sessions (session_key, org_id, project_id, session_id) VALUES ('org-a/proj-a/s1', 'org-a', 'proj-a', 's1')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO episodes (uid, session_key, session_id, producer_id, producer_role, content, content_type, episode_type) VALUES ('e1', 'org-a/proj-a/s1', 's1', 'u1', 'user', 'hello', 'string', 'message')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO episodes (uid, session_key, session_id, producer_id, producer_role, content, content_type, episode_type, deleted) VALUES ('e2', 'org-a/proj-a/s1', 's1', 'u1', 'user', 'hidden', 'string', 'message', 1)"
            )
        )

    count = await store.get_episode_count("org-a", "proj-a")

    assert count == 1

    await factory.dispose()
