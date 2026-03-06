from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.memory.short_term_memory import ShortTermMemory, ShortTermMessage
from memlite.storage.session_store import SqliteSessionStore
from memlite.storage.sqlite_engine import SqliteEngineFactory


async def build_memory(tmp_path: Path, *, capacity: int = 20) -> ShortTermMemory:
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memlite.sqlite3"))
    await factory.initialize_schema()
    store = SqliteSessionStore(factory)
    await store.create_session(
        session_key="org/proj/s1",
        org_id="org",
        project_id="proj",
        session_id="s1",
    )
    memory = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=store,
        message_capacity=capacity,
    )
    memory._test_factory = factory  # type: ignore[attr-defined]
    return memory


@pytest.mark.anyio
async def test_add_messages_tracks_length(tmp_path: Path):
    memory = await build_memory(tmp_path, capacity=100)

    overflow = await memory.add_messages(
        [ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user")]
    )

    assert overflow is False
    assert memory.current_message_length == 5
    assert len(memory.get_messages()) == 1

    await memory._test_factory.dispose()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_capacity_overflow_triggers_summary(tmp_path: Path):
    memory = await build_memory(tmp_path, capacity=10)

    overflow = await memory.add_messages(
        [
            ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user"),
            ShortTermMessage(uid="2", content="world!", producer_id="u1", producer_role="assistant"),
        ]
    )

    assert overflow is True
    assert memory.summary != ""
    assert memory.current_message_length <= memory.message_capacity

    await memory._test_factory.dispose()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_summary_persistence_and_restore(tmp_path: Path):
    memory = await build_memory(tmp_path, capacity=10)

    await memory.add_messages(
        [
            ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user"),
            ShortTermMessage(uid="2", content="world!", producer_id="u1", producer_role="assistant"),
        ]
    )
    await memory.close()

    restored = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=memory._session_store,  # type: ignore[attr-defined]
        message_capacity=10,
    )

    assert restored.summary == memory.summary

    await memory._test_factory.dispose()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_close_and_reset_behaviour(tmp_path: Path):
    memory = await build_memory(tmp_path, capacity=100)
    await memory.add_messages(
        [ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user")]
    )
    await memory.close()

    with pytest.raises(RuntimeError):
        await memory.add_messages(
            [ShortTermMessage(uid="2", content="world", producer_id="u1", producer_role="user")]
        )

    reopened = await ShortTermMemory.create(
        session_key="org/proj/s1",
        session_store=memory._session_store,  # type: ignore[attr-defined]
        message_capacity=100,
    )
    await reopened.reset()

    assert reopened.summary == ""
    assert reopened.get_messages() == []

    await memory._test_factory.dispose()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_delete_episode_removes_single_message(tmp_path: Path):
    memory = await build_memory(tmp_path, capacity=100)
    await memory.add_messages(
        [
            ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user"),
            ShortTermMessage(uid="2", content="world", producer_id="u1", producer_role="assistant"),
        ]
    )

    deleted = await memory.delete_episode("1")

    assert deleted is True
    assert [message.uid for message in memory.get_messages()] == ["2"]
    assert memory.current_message_length == len("world")

    await memory._test_factory.dispose()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_get_context_returns_summary_and_messages(tmp_path: Path):
    memory = await build_memory(tmp_path, capacity=10)
    await memory.add_messages(
        [
            ShortTermMessage(uid="1", content="hello", producer_id="u1", producer_role="user"),
            ShortTermMessage(uid="2", content="world!", producer_id="u1", producer_role="assistant"),
        ]
    )
    context = memory.get_context()

    assert "Summary:" in context
    assert "assistant: world!" in context

    await memory._test_factory.dispose()  # type: ignore[attr-defined]
