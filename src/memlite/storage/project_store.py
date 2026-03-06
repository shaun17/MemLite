"""SQLite-backed project store."""

from dataclasses import dataclass

from sqlalchemy import text

from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.transactions import run_in_transaction


@dataclass(slots=True)
class ProjectRecord:
    """Project metadata record."""

    org_id: str
    project_id: str
    description: str | None
    created_at: str
    updated_at: str


class SqliteProjectStore:
    """Store projects in SQLite."""

    def __init__(self, engine_factory: SqliteEngineFactory) -> None:
        self._engine_factory = engine_factory

    async def create_project(
        self, org_id: str, project_id: str, description: str | None = None
    ) -> None:
        async def _create(session):
            await session.execute(
                text(
                    """
                    INSERT INTO projects (org_id, project_id, description)
                    VALUES (:org_id, :project_id, :description)
                    ON CONFLICT(org_id, project_id)
                    DO UPDATE SET
                        description = excluded.description,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "org_id": org_id,
                    "project_id": project_id,
                    "description": description,
                },
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _create)

    async def get_project(self, org_id: str, project_id: str) -> ProjectRecord | None:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT org_id, project_id, description, created_at, updated_at
                        FROM projects
                        WHERE org_id = :org_id AND project_id = :project_id
                        """
                    ),
                    {"org_id": org_id, "project_id": project_id},
                )
            ).mappings().first()

        if row is None:
            return None

        return ProjectRecord(**row)

    async def list_projects(self, org_id: str | None = None) -> list[ProjectRecord]:
        engine = self._engine_factory.create_engine()
        query = (
            "SELECT org_id, project_id, description, created_at, updated_at FROM projects"
        )
        params: dict[str, str] = {}
        if org_id is not None:
            query += " WHERE org_id = :org_id"
            params["org_id"] = org_id
        query += " ORDER BY org_id, project_id"

        async with engine.connect() as conn:
            rows = (await conn.execute(text(query), params)).mappings().all()

        return [ProjectRecord(**row) for row in rows]

    async def delete_project(self, org_id: str, project_id: str) -> None:
        async def _delete(session):
            await session.execute(
                text(
                    "DELETE FROM projects WHERE org_id = :org_id AND project_id = :project_id"
                ),
                {"org_id": org_id, "project_id": project_id},
            )

        await run_in_transaction(self._engine_factory.create_session_factory(), _delete)

    async def get_episode_count(self, org_id: str, project_id: str) -> int:
        engine = self._engine_factory.create_engine()
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM episodes e
                        JOIN sessions s ON s.session_key = e.session_key
                        WHERE s.org_id = :org_id AND s.project_id = :project_id
                          AND e.deleted = 0
                        """
                    ),
                    {"org_id": org_id, "project_id": project_id},
                )
            ).scalar_one()
        return int(count)
