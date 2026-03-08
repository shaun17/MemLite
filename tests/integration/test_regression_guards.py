from pathlib import Path

import pytest

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings


@pytest.mark.anyio
async def test_search_ordering_remains_stable(tmp_path: Path):
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
        user_id="user-1",
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
            },
            {
                "uid": "ep-2",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 2,
                "content": "Ramen is a comfort food.",
            },
        ],
    )

    first = await resources.orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        mode="episodic",
    )
    second = await resources.orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        mode="episodic",
    )

    assert [item.identifier for item in first.combined] == ["ep-1", "ep-2"]
    assert [item.identifier for item in second.combined] == ["ep-1", "ep-2"]

    await resources.close()


@pytest.mark.anyio
async def test_filter_semantics_remain_stable(tmp_path: Path):
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
        user_id="user-1",
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
                "episode_type": "message",
            },
            {
                "uid": "ep-2",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "assistant-1",
                "producer_role": "assistant",
                "sequence_num": 2,
                "content": "I will remember your ramen food preference.",
                "episode_type": "message",
            },
        ],
    )

    filtered = await resources.orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        mode="episodic",
        producer_role="assistant",
        episode_type="message",
    )

    assert [item.identifier for item in filtered.combined] == ["ep-2"]

    await resources.close()


@pytest.mark.anyio
async def test_delete_leaves_no_residue(tmp_path: Path):
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
        user_id="user-1",
    )
    await resources.orchestrator.add_episodes(
        session_key="session-a",
        semantic_set_id="session-a",
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
    await resources.orchestrator.delete_episodes(
        episode_uids=["ep-1"],
        semantic_set_id="session-a",
    )

    after_search = await resources.orchestrator.search_memories(
        query="food ramen",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
    )
    graph_nodes = await resources.graph_store.search_matching_nodes(node_table="Derivative")
    vector_report = await resources.background_tasks.run_startup_recovery()

    assert after_search.combined == []
    assert graph_nodes == []
    assert vector_report["repair_queue_size"] == 0

    await resources.close()
