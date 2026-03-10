from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.storage.session_store import SqliteSessionStore
from memolite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_session_store_persists_summary_for_reloads(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()

    store = SqliteSessionStore(factory)
    await store.create_session(
        session_key="org-a/proj-a/s1",
        org_id="org-a",
        project_id="proj-a",
        session_id="s1",
        summary="boot summary",
    )
    await factory.dispose()

    reloaded_factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    reloaded_store = SqliteSessionStore(reloaded_factory)
    restored = await reloaded_store.get_session("org-a/proj-a/s1")

    assert restored is not None
    assert restored.summary == "boot summary"

    await reloaded_factory.dispose()
