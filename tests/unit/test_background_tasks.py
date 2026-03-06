from pathlib import Path

import pytest

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings


@pytest.mark.anyio
async def test_startup_recovery_sets_backlog_and_repair_queue(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
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
            sqlite_path=tmp_path / "memlite.sqlite3",
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
