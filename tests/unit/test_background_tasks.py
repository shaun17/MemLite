from pathlib import Path

import pytest

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings


@pytest.mark.anyio
async def test_startup_recovery_sets_backlog_and_repair_queue(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memolite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    await resources.initialize()
    await resources.semantic_feature_store.add_history_to_set("set-a", "ep-1")

    result = await resources.background_tasks.run_startup_recovery()

    assert result["ingestion_backlog"] == 1
    assert resources.metrics.snapshot()["counters"]["ingestion_backlog"] == 1
    await resources.close()


@pytest.mark.anyio
async def test_compensation_pass_marks_pending_history_ingested(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memolite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    await resources.initialize()
    await resources.semantic_feature_store.add_history_to_set("set-a", "ep-1")
    await resources.semantic_feature_store.add_history_to_set("set-a", "ep-2")

    processed = await resources.background_tasks.run_compensation_pass()

    assert processed == 2
    assert resources.metrics.snapshot()["counters"]["ingestion_backlog"] == 0
    assert (
        await resources.semantic_feature_store.get_history_messages(
            set_ids=["set-a"], is_ingested=False
        )
    ) == []
    await resources.close()


@pytest.mark.anyio
async def test_compensation_pass_extracts_basic_semantic_features(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memolite.sqlite3",
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
        semantic_set_id="set-a",
        episodes=[
            {
                "uid": "ep-1",
                "session_key": "session-a",
                "session_id": "session-a",
                "producer_id": "user-1",
                "producer_role": "user",
                "sequence_num": 1,
                "content": "My name is Wenren. I love ramen.",
            }
        ],
    )

    processed = await resources.background_tasks.run_compensation_pass()
    features = await resources.semantic_service.semantic_list(set_id="set-a")
    names = {feature.feature_name for feature in features}

    assert processed >= 1
    assert "name" in names
    assert "favorite_preference" in names
    await resources.close()
