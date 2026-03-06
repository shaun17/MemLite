"""Background compensation and recovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from memlite.semantic.service import SemanticIngestionWorker
from memlite.tools.migration import reconcile_runtime

if TYPE_CHECKING:
    from memlite.app.resources import ResourceManager


async def _noop_history_processor(_set_id: str, history_ids: list[str]) -> int:
    """Default placeholder ingestion processor."""
    return len(history_ids)


@dataclass
class BackgroundTaskRunner:
    """Run lightweight startup recovery and compensation passes."""

    resources: ResourceManager

    async def run_startup_recovery(self) -> dict[str, int]:
        """Refresh backlog metrics and compute repair queue size."""
        pending_set_ids = await self.resources.semantic_feature_store.get_history_set_ids()
        self.resources.metrics.set_gauge("ingestion_backlog", len(pending_set_ids))

        report = await reconcile_runtime(self.resources)
        repair_queue_size = sum(
            len(value) for value in report.values() if isinstance(value, list)
        )
        self.resources.metrics.set_gauge("repair_queue_size", repair_queue_size)
        self.resources.metrics.increment("startup_recovery_runs_total")
        return {
            "ingestion_backlog": len(pending_set_ids),
            "repair_queue_size": repair_queue_size,
        }

    async def run_compensation_pass(self) -> int:
        """Run one semantic ingestion compensation pass."""
        pending_set_ids = await self.resources.semantic_feature_store.get_history_set_ids()
        worker = SemanticIngestionWorker(
            feature_store=self.resources.semantic_feature_store,
            processor=_noop_history_processor,
        )
        processed = 0
        for set_id in pending_set_ids:
            processed += await worker.process_pending(set_id)
        remaining = await self.resources.semantic_feature_store.get_history_set_ids()
        self.resources.metrics.set_gauge("ingestion_backlog", len(remaining))
        self.resources.metrics.increment("compensation_pass_runs_total")
        self.resources.metrics.increment("compensation_items_processed_total", processed)
        return processed
