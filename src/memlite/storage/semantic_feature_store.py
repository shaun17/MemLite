"""SQLite-backed semantic feature store."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.sqlite_vec import SqliteVecIndex
from memlite.storage.transactions import run_in_transaction


@dataclass(slots=True)
class SemanticFeatureRecord:
    id: int
    set_id: str
    category: str
    tag: str
    feature_name: str
    value: str
    metadata_json: str | None
    created_at: str
    updated_at: str
    deleted: int


class SqliteSemanticFeatureStore:
    """Store semantic features, citations, history and embeddings."""

    def __init__(self, engine_factory: SqliteEngineFactory) -> None:
        self._engine_factory = engine_factory
        self._vector_index = SqliteVecIndex(engine_factory, "semantic_feature_vectors")

    async def initialize(self) -> None:
        """Initialize dependent vector tables."""
        await self._vector_index.initialize()

    async def add_feature(
        self,
        *,
        set_id: str,
        category: str,
        tag: str,
        feature_name: str,
        value: str,
        metadata_json: str | None = None,
        embedding: list[float] | None = None,
    ) -> int:
        async def _add(session):
            result = await session.execute(
                text(
                    """
                    INSERT INTO semantic_features (
                        set_id, category, tag, feature_name, value, metadata_json
                    ) VALUES (
                        :set_id, :category, :tag, :feature_name, :value, :metadata_json
                    )
                    RETURNING id
                    """
                ),
                {
                    "set_id": set_id,
                    "category": category,
                    "tag": tag,
                    "feature_name": feature_name,
                    "value": value,
                    "metadata_json": metadata_json,
                },
            )
            return int(result.scalar_one())

        feature_id = await run_in_transaction(
            self._engine_factory.create_session_factory(), _add
        )
        if embedding is not None:
            await self._vector_index.upsert(feature_id, embedding)
        return feature_id

    async def get_feature(self, feature_id: int) -> SemanticFeatureRecord | None:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT id, set_id, category, tag, feature_name, value,
                               metadata_json, created_at, updated_at, deleted
                        FROM semantic_features
                        WHERE id = :feature_id
                        """
                    ),
                    {"feature_id": feature_id},
                )
            ).mappings().first()
        return None if row is None else SemanticFeatureRecord(**row)

    async def update_feature(
        self,
        feature_id: int,
        *,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        feature_name: str | None = None,
        value: str | None = None,
        metadata_json: str | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        fields = {
            "set_id": set_id,
            "category": category,
            "tag": tag,
            "feature_name": feature_name,
            "value": value,
            "metadata_json": metadata_json,
        }
        assignments = [
            f"{key} = :{key}" for key, val in fields.items() if val is not None
        ]
        params = {key: value for key, value in fields.items() if value is not None}
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            params["feature_id"] = feature_id

            async def _update(session):
                await session.execute(
                    text(
                        f"UPDATE semantic_features SET {', '.join(assignments)} WHERE id = :feature_id"
                    ),
                    params,
                )

            await run_in_transaction(
                self._engine_factory.create_session_factory(), _update
            )

        if embedding is not None:
            await self._vector_index.upsert(feature_id, embedding)

    async def delete_features(self, feature_ids: list[int]) -> None:
        if not feature_ids:
            return
        placeholders = ", ".join(f":id_{idx}" for idx in range(len(feature_ids)))
        params = {f"id_{idx}": value for idx, value in enumerate(feature_ids)}

        async def _delete(session):
            await session.execute(
                text(
                    f"UPDATE semantic_features SET deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})"
                ),
                params,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def get_feature_set(
        self,
        *,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        feature_name: str | None = None,
        include_deleted: bool = False,
        page_size: int | None = None,
        page_num: int | None = None,
    ) -> list[SemanticFeatureRecord]:
        return await self.query_features(
            set_id=set_id,
            category=category,
            tag=tag,
            feature_name=feature_name,
            include_deleted=include_deleted,
            page_size=page_size,
            page_num=page_num,
        )

    async def delete_feature_set(
        self,
        *,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        feature_name: str | None = None,
    ) -> None:
        features = await self.query_features(
            set_id=set_id,
            category=category,
            tag=tag,
            feature_name=feature_name,
            include_deleted=False,
        )
        await self.delete_features([feature.id for feature in features])

    async def query_features(
        self,
        *,
        set_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        feature_name: str | None = None,
        include_deleted: bool = False,
        page_size: int | None = None,
        page_num: int | None = None,
    ) -> list[SemanticFeatureRecord]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        for key, value in {
            "set_id": set_id,
            "category": category,
            "tag": tag,
            "feature_name": feature_name,
        }.items():
            if value is not None:
                clauses.append(f"{key} = :{key}")
                params[key] = value
        if not include_deleted:
            clauses.append("deleted = 0")

        query = (
            "SELECT id, set_id, category, tag, feature_name, value, metadata_json, created_at, updated_at, deleted "
            "FROM semantic_features"
        )
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id"
        if page_size is not None:
            params["limit"] = page_size
            params["offset"] = max((page_num or 0), 0) * page_size
            query += " LIMIT :limit OFFSET :offset"

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).mappings().all()
        return [SemanticFeatureRecord(**row) for row in rows]

    async def add_citations(self, feature_id: int, history_ids: list[str]) -> None:
        async def _insert(session):
            for history_id in history_ids:
                await session.execute(
                    text(
                        "INSERT OR IGNORE INTO semantic_citations (feature_id, episode_id) VALUES (:feature_id, :episode_id)"
                    ),
                    {"feature_id": feature_id, "episode_id": history_id},
                )

        await run_in_transaction(self._engine_factory.create_session_factory(), _insert)

    async def get_citations(self, feature_id: int) -> list[str]:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT episode_id FROM semantic_citations WHERE feature_id = :feature_id ORDER BY episode_id"
                    ),
                    {"feature_id": feature_id},
                )
            ).all()
        return [str(row[0]) for row in rows]

    async def get_feature_ids_by_history_ids(self, history_ids: list[str]) -> list[int]:
        """Return feature ids cited by the given episode/history ids."""
        if not history_ids:
            return []
        placeholders = ", ".join(
            f":history_id_{idx}" for idx in range(len(history_ids))
        )
        params = {
            f"history_id_{idx}": history_id
            for idx, history_id in enumerate(history_ids)
        }
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT DISTINCT feature_id
                        FROM semantic_citations
                        WHERE episode_id IN ({placeholders})
                        ORDER BY feature_id
                        """
                    ),
                    params,
                )
            ).all()
        return [int(row[0]) for row in rows]

    async def get_orphan_feature_ids(self, feature_ids: list[int]) -> list[int]:
        """Return feature ids that no longer have any citations."""
        if not feature_ids:
            return []
        placeholders = ", ".join(
            f":feature_id_{idx}" for idx in range(len(feature_ids))
        )
        params = {
            f"feature_id_{idx}": feature_id
            for idx, feature_id in enumerate(feature_ids)
        }
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT f.id
                        FROM semantic_features f
                        LEFT JOIN semantic_citations c ON c.feature_id = f.id
                        WHERE f.id IN ({placeholders})
                        GROUP BY f.id
                        HAVING COUNT(c.episode_id) = 0
                        ORDER BY f.id
                        """
                    ),
                    params,
                )
            ).all()
        return [int(row[0]) for row in rows]

    async def get_history_messages(
        self,
        *,
        set_ids: list[str] | None = None,
        limit: int | None = None,
        is_ingested: bool | None = None,
    ) -> list[str]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if set_ids:
            placeholders = ", ".join(f":set_id_{idx}" for idx in range(len(set_ids)))
            clauses.append(f"set_id IN ({placeholders})")
            params.update(
                {f"set_id_{idx}": value for idx, value in enumerate(set_ids)}
            )
        if is_ingested is not None:
            clauses.append("ingested = :ingested")
            params["ingested"] = int(is_ingested)

        query = "SELECT history_id FROM semantic_set_ingested_history"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, history_id"
        if limit is not None:
            query += " LIMIT :limit"
            params["limit"] = limit

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).all()
        return [str(row[0]) for row in rows]

    async def get_history_messages_count(
        self,
        *,
        set_ids: list[str] | None = None,
        is_ingested: bool | None = None,
    ) -> int:
        messages = await self.get_history_messages(
            set_ids=set_ids,
            is_ingested=is_ingested,
        )
        return len(messages)

    async def add_history_to_set(self, set_id: str, history_id: str) -> None:
        async def _insert(session):
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO semantic_set_ingested_history (set_id, history_id, ingested, created_at) VALUES (:set_id, :history_id, 0, :created_at)"
                ),
                {
                    "set_id": set_id,
                    "history_id": history_id,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _insert)

    async def delete_history(self, history_ids: list[str]) -> None:
        if not history_ids:
            return
        placeholders = ", ".join(
            f":history_id_{idx}" for idx in range(len(history_ids))
        )
        params = {
            f"history_id_{idx}": value for idx, value in enumerate(history_ids)
        }

        async def _delete(session):
            await session.execute(
                text(
                    f"DELETE FROM semantic_set_ingested_history WHERE history_id IN ({placeholders})"
                ),
                params,
            )
            await session.execute(
                text(
                    f"DELETE FROM semantic_citations WHERE episode_id IN ({placeholders})"
                ),
                params,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def mark_messages_ingested(
        self, *, set_id: str, history_ids: list[str]
    ) -> None:
        if not history_ids:
            return
        placeholders = ", ".join(
            f":history_id_{idx}" for idx in range(len(history_ids))
        )
        params = {
            f"history_id_{idx}": value for idx, value in enumerate(history_ids)
        }
        params["set_id"] = set_id

        async def _mark(session):
            await session.execute(
                text(
                    f"UPDATE semantic_set_ingested_history SET ingested = 1 WHERE set_id = :set_id AND history_id IN ({placeholders})"
                ),
                params,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _mark)

    async def get_history_set_ids(
        self,
        *,
        min_uningested_messages: int | None = None,
    ) -> list[str]:
        query = (
            "SELECT set_id FROM semantic_set_ingested_history WHERE ingested = 0 "
            "GROUP BY set_id"
        )
        params: dict[str, Any] = {}
        if min_uningested_messages is not None:
            query += " HAVING COUNT(*) >= :min_count"
            params["min_count"] = min_uningested_messages
        query += " ORDER BY set_id"

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).all()
        return [str(row[0]) for row in rows]

    async def get_set_ids_starts_with(self, prefix: str) -> list[str]:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT DISTINCT set_id FROM semantic_features WHERE set_id LIKE :prefix ORDER BY set_id"
                    ),
                    {"prefix": f"{prefix}%"},
                )
            ).all()
        return [str(row[0]) for row in rows]

    @property
    def vector_index(self) -> SqliteVecIndex:
        return self._vector_index
