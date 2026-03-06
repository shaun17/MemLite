"""SQLite-backed session store."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.transactions import run_in_transaction


@dataclass(slots=True)
class SessionRecord:
    """Session metadata record."""

    session_key: str
    org_id: str
    project_id: str
    session_id: str
    user_id: str | None
    agent_id: str | None
    group_id: str | None
    summary: str
    summary_updated_at: str | None
    created_at: str
    updated_at: str


class SqliteSessionStore:
    """Store sessions and short-term summaries in SQLite."""

    def __init__(self, engine_factory: SqliteEngineFactory) -> None:
        self._engine_factory = engine_factory

    async def create_session(
        self,
        *,
        session_key: str,
        org_id: str,
        project_id: str,
        session_id: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        group_id: str | None = None,
        summary: str = "",
    ) -> None:
        async def _create(session):
            await session.execute(
                text(
                    """
                    INSERT INTO sessions (
                        session_key, org_id, project_id, session_id,
                        user_id, agent_id, group_id, summary, summary_updated_at
                    ) VALUES (
                        :session_key, :org_id, :project_id, :session_id,
                        :user_id, :agent_id, :group_id, :summary,
                        CASE WHEN :summary = '' THEN NULL ELSE CURRENT_TIMESTAMP END
                    )
                    ON CONFLICT(session_key)
                    DO UPDATE SET
                        org_id = excluded.org_id,
                        project_id = excluded.project_id,
                        session_id = excluded.session_id,
                        user_id = excluded.user_id,
                        agent_id = excluded.agent_id,
                        group_id = excluded.group_id,
                        summary = excluded.summary,
                        summary_updated_at = excluded.summary_updated_at,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "session_key": session_key,
                    "org_id": org_id,
                    "project_id": project_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "group_id": group_id,
                    "summary": summary,
                },
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _create)

    async def get_session(self, session_key: str) -> SessionRecord | None:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT session_key, org_id, project_id, session_id,
                               user_id, agent_id, group_id, summary,
                               summary_updated_at, created_at, updated_at
                        FROM sessions
                        WHERE session_key = :session_key
                        """
                    ),
                    {"session_key": session_key},
                )
            ).mappings().first()
        if row is None:
            return None
        return SessionRecord(**row)

    async def delete_session(self, session_key: str) -> None:
        async def _delete(session):
            await session.execute(
                text("DELETE FROM sessions WHERE session_key = :session_key"),
                {"session_key": session_key},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def update_session_metadata(
        self,
        session_key: str,
        **fields: Any,
    ) -> None:
        allowed_fields = {"user_id", "agent_id", "group_id", "summary"}
        updates = {key: value for key, value in fields.items() if key in allowed_fields}
        if not updates:
            return

        assignments = [f"{key} = :{key}" for key in updates]
        if "summary" in updates:
            assignments.append(
                "summary_updated_at = CASE WHEN :summary = '' THEN summary_updated_at ELSE CURRENT_TIMESTAMP END"
            )
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        updates["session_key"] = session_key

        async def _update(session):
            await session.execute(
                text(
                    f"UPDATE sessions SET {', '.join(assignments)} WHERE session_key = :session_key"
                ),
                updates,
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _update)

    async def search_sessions(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        group_id: str | None = None,
    ) -> list[SessionRecord]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        for key, value in {
            "org_id": org_id,
            "project_id": project_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "group_id": group_id,
        }.items():
            if value is not None:
                clauses.append(f"{key} = :{key}")
                params[key] = value

        query = (
            "SELECT session_key, org_id, project_id, session_id, user_id, agent_id, "
            "group_id, summary, summary_updated_at, created_at, updated_at FROM sessions"
        )
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, session_key"

        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).mappings().all()
        return [SessionRecord(**row) for row in rows]

    async def update_summary(self, session_key: str, summary: str) -> None:
        await self.update_session_metadata(session_key, summary=summary)
