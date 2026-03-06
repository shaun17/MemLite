from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.episode_store import SqliteEpisodeStore
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_episode_store_supports_pagination_and_reload(tmp_path: Path):
    sqlite_path = tmp_path / "memlite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()
    await SqliteSessionStore(factory).create_session(
        session_key="org/proj/s1",
        org_id="org",
        project_id="proj",
        session_id="s1",
    )
    store = SqliteEpisodeStore(factory)

    await store.add_episodes(
        [
            {
                "uid": f"e{index}",
                "session_key": "org/proj/s1",
                "session_id": "s1",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": index,
                "content": f"content-{index}",
            }
            for index in range(1, 6)
        ]
    )
    await factory.dispose()

    reloaded_factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    reloaded_store = SqliteEpisodeStore(reloaded_factory)
    paged = await reloaded_store.list_episodes(
        session_key="org/proj/s1", limit=2, offset=1
    )

    assert [episode.uid for episode in paged] == ["e2", "e3"]

    await reloaded_factory.dispose()
