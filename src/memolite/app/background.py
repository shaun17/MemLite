"""Background compensation and recovery helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
_ZH_NAME_PATTERN = re.compile(r"(?:我叫|我的名字是)\s*([^\s，。！？；,!.?;]{1,30})")
_ZH_FAVORITE_PATTERN = re.compile(
    r"(?:我(?:最?喜欢|爱吃|喜欢吃|常吃))(?:的)?(?:(食物|饮料|语言|编辑器|框架))?(?:是|有)?\s*([^\n，。！？；,!.?;]{1,80})"
)
_ZH_PREFERENCE_OBJECT_TYPES = {
    "食物": "food",
    "饮料": "drink",
    "语言": "language",
    "编辑器": "editor",
    "框架": "framework",
}

_CJK_DETECT = re.compile(r"[\u4e00-\u9fff]")


def _make_embed_text(
    feature_name: str,
    value: str,
    *,
    use_cjk_prefix_hack: bool = True,
) -> str:
    """Build an embedding-friendly text representation for a feature.

    The Chinese prefix hack only helps the lightweight hash embedder by forcing
    token overlap. Real embedding models should receive the plain feature/value
    text instead.
    """
    if use_cjk_prefix_hack and _CJK_DETECT.search(value):
        if "name" in feature_name:
            return f"叫 {value}"
        return f"喜欢 {value}"
    return f"{feature_name} {value}"


_VACUUM_INTERVAL_PASSES = 500  # run VACUUM every N compensation passes


@dataclass
class BackgroundTaskRunner:
    """Run lightweight startup recovery and compensation passes."""

    resources: ResourceManager
    _pass_count: int = field(default=0, init=False, repr=False)

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
        self._pass_count += 1
        if self._pass_count % _VACUUM_INTERVAL_PASSES == 0:
            await self._run_vacuum()
        return processed

    async def _run_vacuum(self) -> None:
        """Reclaim SQLite space with low-impact maintenance pragmas."""
        from sqlalchemy import text

        engine = self.resources.sqlite.create_engine()
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA wal_checkpoint(PASSIVE)"))
            await conn.execute(text("PRAGMA incremental_vacuum(200)"))
        self.resources.metrics.increment("vacuum_runs_total")

    async def _process_history(self, set_id: str, history_ids: list[str]) -> int:
        """Extract basic semantic features from pending episodic history."""
        episodes = await self.resources.episode_store.get_episodes(history_ids)
        episode_by_uid = {episode.uid: episode for episode in episodes}

        for history_id in history_ids:
            episode = episode_by_uid.get(history_id)
            if episode is None:
                continue
            for category, tag, feature_name, value, embed_text in _extract_features(
                episode.content,
                use_cjk_prefix_hack=self.resources.embedder_provider_name == "hash",
            ):
                metadata = json.dumps({"source": "background_compensation"}, ensure_ascii=False)
                embedding = await self.resources.semantic_service.generate_feature_embedding(
                    embed_text
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


def _extract_features(
    content: str,
    *,
    use_cjk_prefix_hack: bool = True,
) -> list[tuple[str, str, str, str, str]]:
    """Heuristic semantic feature extraction from free text.

    Returns 5-tuples of (category, tag, feature_name, value, embed_text). The
    Chinese overlap hack is reserved for the hash embedder path.
    """
    features: list[tuple[str, str, str, str, str]] = []

    name_match = _NAME_PATTERN.search(content)
    if name_match:
        name = name_match.group(1).strip()
        features.append((
            "profile",
            "identity",
            "name",
            name,
            _make_embed_text("name", name, use_cjk_prefix_hack=use_cjk_prefix_hack),
        ))

    zh_name_match = _ZH_NAME_PATTERN.search(content)
    if zh_name_match:
        name = zh_name_match.group(1).strip()
        features.append((
            "profile",
            "identity",
            "name",
            name,
            _make_embed_text("name", name, use_cjk_prefix_hack=use_cjk_prefix_hack),
        ))

    for match in _FAVORITE_PATTERN.finditer(content):
        object_type = (match.group(1) or "preference").strip().lower()
        raw_value = match.group(2).strip(" .,!?:;\t\n\r")
        if not raw_value:
            continue
        feature_name = f"favorite_{object_type}"
        features.append(
            ("profile", "preference", feature_name, raw_value,
             _make_embed_text(feature_name, raw_value))
        )

    for match in _ZH_FAVORITE_PATTERN.finditer(content):
        object_type = _ZH_PREFERENCE_OBJECT_TYPES.get(
            (match.group(1) or "").strip(),
            "food",
        )
        raw_value = match.group(2).strip(" ，。！？；,!.?;\t\n\r")
        raw_value = re.sub(r"^(?:吃|喝|用|是)\s*", "", raw_value)
        if not raw_value:
            continue
        feature_name = f"favorite_{object_type}"
        features.append(
            (
                "profile",
                "preference",
                feature_name,
                raw_value,
                _make_embed_text(
                    feature_name,
                    raw_value,
                    use_cjk_prefix_hack=use_cjk_prefix_hack,
                ),
            )
        )

    return features
