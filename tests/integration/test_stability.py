from pathlib import Path

import pytest

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings


@pytest.mark.anyio
async def test_delete_episodes_is_idempotent(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    await resources.initialize()
    await resources.orchestrator.create_project(org_id="org-a", project_id="project-a")
    await resources.orchestrator.create_session(
        session_key="session-a",
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
    )
    await resources.orchestrator.add_episodes(
        session_key="session-a",
        episodes=[
            {
                "uid": "ep-1",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 1,
                "content": "Ramen is my favorite food.",
            }
        ],
    )

    await resources.orchestrator.delete_episodes(episode_uids=["ep-1"])
    await resources.orchestrator.delete_episodes(episode_uids=["ep-1"])

    remaining = await resources.episode_store.list_episodes(
        session_key="session-a",
        include_deleted=False,
    )
    deleted = await resources.episode_store.find_matching_episodes(
        session_key="session-a",
        include_deleted=True,
    )

    assert remaining == []
    assert [episode.uid for episode in deleted] == ["ep-1"]
    await resources.close()


@pytest.mark.anyio
async def test_add_episode_is_idempotent(tmp_path: Path):
    settings = Settings(
        sqlite_path=tmp_path / "memlite.sqlite3",
        kuzu_path=tmp_path / "kuzu",
    )
    resources = ResourceManager.create(settings)
    await resources.initialize()
    await resources.session_store.create_session(
        session_key="session-1",
        org_id="org-1",
        project_id="project-1",
        session_id="session-1",
    )

    payload = {
        "uid": "episode-1",
        "session_key": "session-1",
        "session_id": "session-1",
        "producer_id": "user-1",
        "producer_role": "user",
        "sequence_num": 1,
        "content": "same content",
        "content_type": "text",
        "episode_type": "message",
    }
    await resources.episode_store.add_episode(payload)
    await resources.episode_store.add_episode(payload)

    episodes = await resources.episode_store.list_episodes(session_key="session-1")

    assert [episode.uid for episode in episodes] == ["episode-1"]

    await resources.close()
