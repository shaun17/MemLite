from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.memory.short_term_memory import ShortTermMemory, ShortTermMessage
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_short_term_memory_updates_session_summary(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    session_store = SqliteSessionStore(factory)
    await session_store.create_session(
        session_key="org/proj/s1",
        org_id="org",
        project_id="proj",
        session_id="s1",
    )

    memory = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=session_store,
        message_capacity=10,
    )
    await memory.add_messages(
        [
            ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user"),
            ShortTermMessage(uid="2", content="world!", producer_id="u1", producer_role="assistant"),
        ]
    )

    session = await session_store.get_session("org/proj/s1")

    assert session is not None
    assert session.summary != ""

    await factory.dispose()


@pytest.mark.anyio
async def test_short_term_memory_delete_and_context_flow(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    session_store = SqliteSessionStore(factory)
    await session_store.create_session(
        session_key="org/proj/s1",
        org_id="org",
        project_id="proj",
        session_id="s1",
    )

    memory = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=session_store,
        message_capacity=100,
    )
    await memory.add_messages(
        [
            ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user"),
            ShortTermMessage(uid="2", content="world", producer_id="u1", producer_role="assistant"),
        ]
    )

    deleted = await memory.delete_episode("1")
    context = memory.get_context()

    assert deleted is True
    assert "user: hello" not in context
    assert "assistant: world" in context

    await factory.dispose()


@pytest.mark.anyio
async def test_session_close_and_reopen_restores_summary(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memolite.sqlite3"))
    await factory.initialize_schema()
    session_store = SqliteSessionStore(factory)
    await session_store.create_session(
        session_key="org/proj/s1",
        org_id="org",
        project_id="proj",
        session_id="s1",
    )

    first = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=session_store,
        message_capacity=10,
    )
    await first.add_messages(
        [
            ShortTermMessage(
                uid="1",
                content="hello",
                producer_id="u1",
                producer_role="user",
            ),
            ShortTermMessage(
                uid="2",
                content="world!",
                producer_id="u1",
                producer_role="assistant",
            ),
        ]
    )
    await first.close()

    reopened = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=session_store,
        message_capacity=10,
    )
    restored_summary = await reopened.restore_summary()

    assert restored_summary == first.summary
    assert restored_summary != ""
    assert reopened.get_context().startswith("Summary:")

    await factory.dispose()
