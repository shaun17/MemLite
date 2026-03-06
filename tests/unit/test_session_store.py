from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_session_store_crud_and_summary(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memlite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSessionStore(factory)

    await store.create_session(
        session_key="org-a/proj-a/s1",
        org_id="org-a",
        project_id="proj-a",
        session_id="s1",
        user_id="user-1",
        agent_id="agent-1",
    )

    session = await store.get_session("org-a/proj-a/s1")
    assert session is not None
    assert session.user_id == "user-1"
    assert session.summary == ""

    await store.update_session_metadata("org-a/proj-a/s1", group_id="group-1")
    await store.update_summary("org-a/proj-a/s1", "summary text")

    updated = await store.get_session("org-a/proj-a/s1")
    assert updated is not None
    assert updated.group_id == "group-1"
    assert updated.summary == "summary text"
    assert updated.summary_updated_at is not None

    await store.delete_session("org-a/proj-a/s1")
    deleted = await store.get_session("org-a/proj-a/s1")
    assert deleted is None

    await factory.dispose()


@pytest.mark.anyio
async def test_session_store_searches_by_scopes(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memlite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSessionStore(factory)

    await store.create_session(
        session_key="org-a/proj-a/s1",
        org_id="org-a",
        project_id="proj-a",
        session_id="s1",
        user_id="user-1",
        agent_id="agent-1",
        group_id="group-1",
    )
    await store.create_session(
        session_key="org-a/proj-a/s2",
        org_id="org-a",
        project_id="proj-a",
        session_id="s2",
        user_id="user-2",
        agent_id="agent-1",
        group_id="group-2",
    )

    sessions = await store.search_sessions(org_id="org-a", agent_id="agent-1")
    filtered = await store.search_sessions(group_id="group-2")

    assert len(sessions) == 2
    assert [session.session_id for session in filtered] == ["s2"]

    await factory.dispose()
