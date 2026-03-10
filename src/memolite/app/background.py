"""Background compensation and recovery helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from memolite.semantic.service import SemanticIngestionWorker
from memolite.tools.migration import reconcile_runtime

if TYPE_CHECKING:
    from memolite.app.resources import ResourceManager


_NAME_PATTERN = re.compile(r"(?:my name is|i am)\s+([A-Za-z][\w\-]{1,30})", re.IGNORECASE)
_FAVORITE_PATTERN = re.compile(
    r"(?:my favorite\s+(food|drink|language|editor|framework)?\s*is|i (?:like|love|prefer))\s+([^\.!?\n]{1,80})",
    re.IGNORECASE,
)


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
            processor=self._process_history,
        )
        processed = 0
        for set_id in pending_set_ids:
            processed += await worker.process_pending(set_id)
        remaining = await self.resources.semantic_feature_store.get_history_set_ids()
        self.resources.metrics.set_gauge("ingestion_backlog", len(remaining))
        self.resources.metrics.increment("compensation_pass_runs_total")
        self.resources.metrics.increment("compensation_items_processed_total", processed)
        return processed

    async def _process_history(self, set_id: str, history_ids: list[str]) -> int:
        """Extract basic semantic features from pending episodic history."""
        episodes = await self.resources.episode_store.get_episodes(history_ids)
        episode_by_uid = {episode.uid: episode for episode in episodes}

        for history_id in history_ids:
            episode = episode_by_uid.get(history_id)
            if episode is None:
                continue
            for category, tag, feature_name, value in _extract_features(episode.content):
                metadata = json.dumps({"source": "background_compensation"}, ensure_ascii=False)
                embedding = await self.resources.semantic_service.generate_feature_embedding(
                    f"{feature_name} {value}"
                )
                feature_id = await self.resources.semantic_feature_store.add_feature(
                    set_id=set_id,
                    category=category,
                    tag=tag,
                    feature_name=feature_name,
                    value=value,
                    metadata_json=metadata,
                    embedding=embedding,
                )
                await self.resources.semantic_feature_store.add_citations(
                    feature_id,
                    [history_id],
                )
        return len(history_ids)


def _extract_features(content: str) -> list[tuple[str, str, str, str]]:
    """Heuristic semantic feature extraction from free text."""
    features: list[tuple[str, str, str, str]] = []

    name_match = _NAME_PATTERN.search(content)
    if name_match:
        name = name_match.group(1).strip()
        features.append(("profile", "identity", "name", name))

    for match in _FAVORITE_PATTERN.finditer(content):
        object_type = (match.group(1) or "preference").strip().lower()
        raw_value = match.group(2).strip(" .,!?:;\t\n\r")
        if not raw_value:
            continue
        feature_name = f"favorite_{object_type}"
        features.append(("profile", "preference", feature_name, raw_value))

    return features
