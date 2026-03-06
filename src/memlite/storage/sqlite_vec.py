"""Lightweight sqlite-vec compatibility layer for MemLite."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from memlite.common.config import Settings
from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.transactions import run_in_transaction


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

    async def initialize(self) -> None:
        """Ensure the vector table exists."""
        engine = self._engine_factory.create_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        feature_id INTEGER PRIMARY KEY,
                        embedding_json TEXT NOT NULL
                    )
                    """
                )
            )

    async def upsert(self, item_id: int, embedding: list[float]) -> None:
        """Insert or replace a single embedding."""
        await self.batch_upsert([(item_id, embedding)])

    async def batch_upsert(self, items: list[tuple[int, list[float]]]) -> None:
        """Insert or replace multiple embeddings."""
        async def _upsert(session: AsyncSession) -> None:
            for item_id, embedding in items:
                await session.execute(
                    text(
                        f"""
                        INSERT INTO {self._table_name} (feature_id, embedding_json)
                        VALUES (:feature_id, :embedding_json)
                        ON CONFLICT(feature_id)
                        DO UPDATE SET embedding_json = excluded.embedding_json
                        """
                    ),
                    {
                        "feature_id": item_id,
                        "embedding_json": json.dumps(embedding),
                    },
                )

        await run_in_transaction(self._engine_factory.create_session_factory(), _upsert)

    async def search_top_k(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[VectorSearchResult]:
        """Return top-k vectors ranked by cosine similarity."""
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"SELECT feature_id, embedding_json FROM {self._table_name}"
                    )
                )
            ).all()

        results = []
        for feature_id, embedding_json in rows:
            embedding = json.loads(embedding_json)
            score = _cosine_similarity(query_embedding, embedding)
            results.append(VectorSearchResult(item_id=int(feature_id), score=score))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

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
