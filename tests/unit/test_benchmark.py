from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.tools.benchmark import benchmark_search_workload


@pytest.mark.anyio
async def test_benchmark_search_workload_returns_latency_report(tmp_path: Path):
    report = await benchmark_search_workload(
        settings=Settings(
            sqlite_path=tmp_path / "memolite.sqlite3",
            kuzu_path=tmp_path / "kuzu",
        ),
        episode_count=3,
        query_iterations=2,
    )

    assert report["episode_count"] == 3
    assert report["query_iterations"] == 2
    assert report["episodic_avg_latency_ms"] >= 0
    assert report["semantic_avg_latency_ms"] >= 0
