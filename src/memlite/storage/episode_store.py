"""SQLite-backed episode store."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.transactions import run_in_transaction


@dataclass(slots=True)
class EpisodeRecord:
    """Episode persistence record."""

    uid: str
    session_key: str
    session_id: str
    producer_id: str
    producer_role: str
    produced_for_id: str | None
    sequence_num: int
    content: str
    content_type: str
    episode_type: str
    created_at: str
    metadata_json: str | None
    filterable_metadata_json: str | None
    deleted: int


class SqliteEpisodeStore:
    """Store episodic records in SQLite."""

    def __init__(self, engine_factory: SqliteEngineFactory) -> None:
        self._engine_factory = engine_factory

    async def add_episode(self, payload: dict[str, Any]) -> None:
        await self.add_episodes([payload])

    async def add_episodes(self, payloads: list[dict[str, Any]]) -> None:
        async def _insert(session):
            for payload in payloads:
                await session.execute(
                    text(
                        """
                        INSERT INTO episodes (
                            uid, session_key, session_id, producer_id, producer_role,
                            produced_for_id, sequence_num, content, content_type,
                            episode_type, metadata_json, filterable_metadata_json, deleted
                        ) VALUES (
                            :uid, :session_key, :session_id, :producer_id, :producer_role,
                            :produced_for_id, :sequence_num, :content, :content_type,
                            :episode_type, :metadata_json, :filterable_metadata_json, :deleted
                        )
                        """
                    ),
                    {
                        "uid": payload["uid"],
                        "session_key": payload["session_key"],
                        "session_id": payload["session_id"],
                        "producer_id": payload["producer_id"],
                        "producer_role": payload["producer_role"],
                        "produced_for_id": payload.get("produced_for_id"),
                        "sequence_num": payload.get("sequence_num", 0),
                        "content": payload["content"],
                        "content_type": payload.get("content_type", "string"),
                        "episode_type": payload.get("episode_type", "message"),
                        "metadata_json": payload.get("metadata_json"),
                        "filterable_metadata_json": payload.get(
                            "filterable_metadata_json"
                        ),
                        "deleted": payload.get("deleted", 0),
                    },
                )

        await run_in_transaction(self._engine_factory.create_session_factory(), _insert)

    async def get_episodes(self, uids: list[str]) -> list[EpisodeRecord]:
        if not uids:
            return []
        placeholders = ", ".join(f":uid_{idx}" for idx in range(len(uids)))
        params = {f"uid_{idx}": uid for idx, uid in enumerate(uids)}
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT uid, session_key, session_id, producer_id, producer_role,
                               produced_for_id, sequence_num, content, content_type,
                               episode_type, created_at, metadata_json,
                               filterable_metadata_json, deleted
                        FROM episodes
                        WHERE uid IN ({placeholders})
                        ORDER BY created_at, uid
                        """
                    ),
                    params,
                )
            ).mappings().all()
        return [EpisodeRecord(**row) for row in rows]

    async def list_episodes(
        self,
        *,
        session_key: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[EpisodeRecord]:
        clauses: list[str] = []
        params: dict[str, Any] = {"offset": offset}
        if session_key is not None:
            clauses.append("session_key = :session_key")
            params["session_key"] = session_key
        if not include_deleted:
            clauses.append("deleted = 0")

        query = (
            "SELECT uid, session_key, session_id, producer_id, producer_role, "
            "produced_for_id, sequence_num, content, content_type, episode_type, "
            "created_at, metadata_json, filterable_metadata_json, deleted FROM episodes"
        )
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY sequence_num, created_at, uid"
        if limit is not None:
            query += " LIMIT :limit OFFSET :offset"
            params["limit"] = limit

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).mappings().all()
        return [EpisodeRecord(**row) for row in rows]

    async def delete_episodes(self, uids: list[str]) -> None:
        if not uids:
            return
        placeholders = ", ".join(f":uid_{idx}" for idx in range(len(uids)))
        params = {f"uid_{idx}": uid for idx, uid in enumerate(uids)}

        async def _delete(session):
            await session.execute(
                text(
                    f"UPDATE episodes SET deleted = 1 WHERE uid IN ({placeholders}) AND deleted = 0"
                ),
                params,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def delete_session_episodes(self, session_key: str) -> None:
        async def _delete(session):
            await session.execute(
                text(
                    "UPDATE episodes SET deleted = 1 WHERE session_key = :session_key AND deleted = 0"
                ),
                {"session_key": session_key},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def purge_episodes(self, uids: list[str]) -> None:
        """Physically delete episodes by uid."""
        if not uids:
            return
        placeholders = ", ".join(f":uid_{idx}" for idx in range(len(uids)))
        params = {f"uid_{idx}": uid for idx, uid in enumerate(uids)}

        async def _delete(session):
            await session.execute(
                text(f"DELETE FROM episodes WHERE uid IN ({placeholders})"),
                params,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def purge_session_episodes(self, session_key: str) -> None:
        """Physically delete all episodes for a session."""

        async def _delete(session):
            await session.execute(
                text("DELETE FROM episodes WHERE session_key = :session_key"),
                {"session_key": session_key},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def count_episodes(
        self, *, session_key: str | None = None, include_deleted: bool = False
    ) -> int:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if session_key is not None:
            clauses.append("session_key = :session_key")
            params["session_key"] = session_key
        if not include_deleted:
            clauses.append("deleted = 0")

        query = "SELECT COUNT(*) FROM episodes"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            count = (await conn.execute(text(query), params)).scalar_one()
        return int(count)

    async def find_matching_episodes(
        self,
        *,
        session_key: str | None = None,
        producer_role: str | None = None,
        episode_type: str | None = None,
        include_deleted: bool = False,
    ) -> list[EpisodeRecord]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        for key, value in {
            "session_key": session_key,
            "producer_role": producer_role,
            "episode_type": episode_type,
        }.items():
            if value is not None:
                clauses.append(f"{key} = :{key}")
                params[key] = value
        if not include_deleted:
            clauses.append("deleted = 0")

        query = (
            "SELECT uid, session_key, session_id, producer_id, producer_role, "
            "produced_for_id, sequence_num, content, content_type, episode_type, "
            "created_at, metadata_json, filterable_metadata_json, deleted FROM episodes"
        )
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY sequence_num, created_at, uid"

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).mappings().all()
        return [EpisodeRecord(**row) for row in rows]
