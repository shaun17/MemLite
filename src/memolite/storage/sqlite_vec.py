"""Lightweight sqlite-vec compatibility layer for MemLite."""

from __future__ import annotations

import heapq
import json  # retained for migration of legacy embedding_json rows
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from memolite.common.config import Settings
from memolite.storage.sqlite_engine import SqliteEngineFactory
from memolite.storage.transactions import run_in_transaction


@dataclass(slots=True)
class VectorSearchResult:
    """Search result for vector similarity lookup."""

    item_id: int
    score: float


class SqliteVecExtensionLoader:
    """Detect and optionally load a sqlite-vec extension."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def detect_extension(self) -> Path | None:
        """Return the extension path if configured and present."""
        path = self._settings.sqlite_vec_extension_path
        if path is None:
            return None
        return path if path.exists() else None

    def is_available(self) -> bool:
        """Return whether a native sqlite-vec extension is available."""
        return self.detect_extension() is not None


class SqliteVecIndex:
    """Vector index backed by SQLite tables, with Python similarity fallback."""

    def __init__(self, engine_factory: SqliteEngineFactory, table_name: str) -> None:
        self._engine_factory = engine_factory
        self._table_name = table_name
        self._metrics = None

    def bind_metrics(self, metrics) -> None:  # type: ignore[no-untyped-def]
        self._metrics = metrics

    async def initialize(self) -> None:
        """Ensure the vector table exists and migrate legacy JSON embeddings."""
        engine = self._engine_factory.create_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        feature_id INTEGER PRIMARY KEY,
                        embedding BLOB NOT NULL
                    )
                    """
                )
            )
        await self._migrate_json_to_blob()

    async def _migrate_json_to_blob(self) -> None:
        """One-time migration: convert legacy JSON TEXT embeddings to BLOB."""
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT COUNT(*) FROM pragma_table_info('{self._table_name}') WHERE name='embedding_json'"
                )
            )
            row = result.fetchone()
            if row is None or row[0] == 0:
                return  # Already migrated or new database

            rows = (
                await conn.execute(
                    text(f"SELECT feature_id, embedding_json FROM {self._table_name}")
                )
            ).fetchall()

        async with engine.begin() as conn:
            await conn.execute(
                text(f"ALTER TABLE {self._table_name} ADD COLUMN embedding BLOB")
            )
            for feature_id, json_str in rows:
                vec = json.loads(json_str)
                blob = struct.pack(f"{len(vec)}f", *vec)
                await conn.execute(
                    text(
                        f"UPDATE {self._table_name} SET embedding=:blob WHERE feature_id=:fid"
                    ),
                    {"blob": blob, "fid": feature_id},
                )
            await conn.execute(
                text(
                    f"CREATE TABLE {self._table_name}_new"
                    f" (feature_id INTEGER PRIMARY KEY, embedding BLOB NOT NULL)"
                )
            )
            await conn.execute(
                text(
                    f"INSERT INTO {self._table_name}_new"
                    f" SELECT feature_id, embedding FROM {self._table_name}"
                )
            )
            await conn.execute(text(f"DROP TABLE {self._table_name}"))
            await conn.execute(
                text(f"ALTER TABLE {self._table_name}_new RENAME TO {self._table_name}")
            )

    async def upsert(self, item_id: int, embedding: list[float]) -> None:
        """Insert or replace a single embedding."""
        await self.batch_upsert([(item_id, embedding)])

    async def batch_upsert(self, items: list[tuple[int, list[float]]]) -> None:
        """Insert or replace multiple embeddings."""
        if not items:
            return

        async def _upsert(session: AsyncSession) -> None:
            await session.execute(
                text(
                    f"""
                    INSERT INTO {self._table_name} (feature_id, embedding)
                    VALUES (:feature_id, :embedding)
                    ON CONFLICT(feature_id)
                    DO UPDATE SET embedding = excluded.embedding
                    """
                ),
                [
                    {
                        "feature_id": item_id,
                        "embedding": struct.pack(f"{len(embedding)}f", *embedding),
                    }
                    for item_id, embedding in items
                ],
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _upsert)

    async def search_top_k(
        self,
        query_embedding: list[float],
        limit: int = 10,
        allowed_item_ids: set[int] | None = None,
    ) -> list[VectorSearchResult]:
        """Return top-k vectors ranked by cosine similarity.

        This is currently a Python fallback that scans all candidate rows loaded
        from SQLite, so it is suitable for lightweight/single-node datasets but
        not for large-scale ANN workloads.
        """
        started = perf_counter()
        if allowed_item_ids is not None and not allowed_item_ids:
            return []
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            if allowed_item_ids is None:
                rows = (
                    await conn.execute(
                        text(
                            f"SELECT feature_id, embedding FROM {self._table_name}"
                        )
                    )
                ).all()
            else:
                placeholders = ", ".join(
                    f":item_id_{idx}" for idx in range(len(allowed_item_ids))
                )
                params = {
                    f"item_id_{idx}": item_id
                    for idx, item_id in enumerate(sorted(allowed_item_ids))
                }
                rows = (
                    await conn.execute(
                        text(
                            f"""
                            SELECT feature_id, embedding
                            FROM {self._table_name}
                            WHERE feature_id IN ({placeholders})
                            """
                        ),
                        params,
                    )
                ).all()

        top_k: list[tuple[float, int]] = []
        for feature_id, embedding_bytes in rows:
            try:
                n = len(embedding_bytes) // 4
                embedding = list(struct.unpack(f"{n}f", embedding_bytes))
            except Exception:
                continue
            score = _cosine_similarity(query_embedding, embedding)
            item = (score, int(feature_id))
            if len(top_k) < max(limit, 1):
                heapq.heappush(top_k, item)
            else:
                heapq.heappushpop(top_k, item)

        ranked = sorted(top_k, key=lambda item: item[0], reverse=True)
        if self._metrics is not None:
            self._metrics.increment("vec_queries_total")
            self._metrics.observe_timing(
                "vec_query_latency_ms",
                (perf_counter() - started) * 1000,
            )
        return [VectorSearchResult(item_id=item_id, score=score) for score, item_id in ranked]

    async def delete(self, item_id: int) -> None:
        """Delete a single embedding by item id."""
        await self.delete_many([item_id])

    async def delete_many(self, item_ids: list[int]) -> None:
        """Delete multiple embeddings by item ids."""
        if not item_ids:
            return

        placeholders = ", ".join(f":item_id_{idx}" for idx in range(len(item_ids)))
        params = {f"item_id_{idx}": item_id for idx, item_id in enumerate(item_ids)}

        async def _delete(session: AsyncSession) -> None:
            await session.execute(
                text(
                    f"DELETE FROM {self._table_name} WHERE feature_id IN ({placeholders})"
                ),
                params,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(lhs * rhs for lhs, rhs in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
