from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.episode_store import SqliteEpisodeStore
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_episode_store_crud_and_count(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    await SqliteSessionStore(factory).create_session(
        session_key="org/proj/s1",
        org_id="org",
        project_id="proj",
        session_id="s1",
    )
    store = SqliteEpisodeStore(factory)

    await store.add_episode(
        {
            "uid": "e1",
            "session_key": "org/proj/s1",
            "session_id": "s1",
            "producer_id": "user-1",
            "producer_role": "user",
            "sequence_num": 1,
            "content": "hello",
        }
    )
    await store.add_episodes(
        [
            {
                "uid": "e2",
                "session_key": "org/proj/s1",
                "session_id": "s1",
                "producer_id": "assistant-1",
                "producer_role": "assistant",
                "sequence_num": 2,
                "content": "hi",
            },
            {
                "uid": "e3",
                "session_key": "org/proj/s1",
                "session_id": "s1",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 3,
                "content": "bye",
                "episode_type": "event",
            },
        ]
    )

    listed = await store.list_episodes(session_key="org/proj/s1")
    fetched = await store.get_episodes(["e1", "e3"])
    count = await store.count_episodes(session_key="org/proj/s1")

    assert [episode.uid for episode in listed] == ["e1", "e2", "e3"]
    assert [episode.uid for episode in fetched] == ["e1", "e3"]
    assert count == 3

    await store.delete_episodes(["e2"])
    remaining = await store.list_episodes(session_key="org/proj/s1")
    deleted_count = await store.count_episodes(
        session_key="org/proj/s1", include_deleted=True
    )

    assert [episode.uid for episode in remaining] == ["e1", "e3"]
    assert deleted_count == 3

    await store.delete_session_episodes("org/proj/s1")
    assert await store.count_episodes(session_key="org/proj/s1") == 0

    await factory.dispose()


@pytest.mark.anyio
async def test_episode_store_filters_matching_records(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
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
                "uid": "e1",
                "session_key": "org/proj/s1",
                "session_id": "s1",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 1,
                "content": "hello",
                "episode_type": "message",
            },
            {
                "uid": "e2",
                "session_key": "org/proj/s1",
                "session_id": "s1",
                "producer_id": "assistant-1",
                "producer_role": "assistant",
                "sequence_num": 2,
                "content": "result",
                "episode_type": "event",
            },
        ]
    )

    matched_role = await store.find_matching_episodes(producer_role="assistant")
    matched_type = await store.find_matching_episodes(episode_type="message")

    assert [episode.uid for episode in matched_role] == ["e2"]
    assert [episode.uid for episode in matched_type] == ["e1"]

    await factory.dispose()
