from pathlib import Path

import pytest
from sqlalchemy import text

from memlite.common.config import Settings
from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.transactions import run_in_transaction


@pytest.mark.anyio
async def test_sqlite_engine_healthcheck_and_pragmas(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    settings = Settings(sqlite_path=sqlite_path)
    factory = SqliteEngineFactory(settings)

    assert await factory.healthcheck() is True

    engine = factory.create_engine()
    async with engine.connect() as conn:
        journal_mode = (await conn.execute(text("PRAGMA journal_mode;"))).scalar_one()
        foreign_keys = (await conn.execute(text("PRAGMA foreign_keys;"))).scalar_one()
        synchronous = (await conn.execute(text("PRAGMA synchronous;"))).scalar_one()
        temp_store = (await conn.execute(text("PRAGMA temp_store;"))).scalar_one()

    assert str(journal_mode).lower() == "wal"
    assert foreign_keys == 1
    assert int(synchronous) == 1
    assert int(temp_store) == 2

    await factory.dispose()


@pytest.mark.anyio
async def test_sqlite_engine_can_initialize_schema(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    settings = Settings(sqlite_path=sqlite_path)
    factory = SqliteEngineFactory(settings)

    await factory.initialize_schema()

    engine = factory.create_engine()
    async with engine.connect() as conn:
        tables = {
            row[0]
            for row in (
                await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            ).all()
        }

    assert {"projects", "sessions", "episodes"}.issubset(tables)

    await factory.dispose()


@pytest.mark.anyio
async def test_run_in_transaction_commits_changes(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    settings = Settings(sqlite_path=sqlite_path)
    factory = SqliteEngineFactory(settings)
    await factory.initialize_schema()
    session_factory = factory.create_session_factory()

    async def insert_project(session):
        await session.execute(
            text(
                "INSERT INTO projects (org_id, project_id, description) VALUES (:org_id, :project_id, :description)"
            ),
            {
                "org_id": "demo-org",
                "project_id": "demo-project",
                "description": "Demo",
            },
        )
        return "ok"

    result = await run_in_transaction(session_factory, insert_project)

    assert result == "ok"

    engine = factory.create_engine()
    async with engine.connect() as conn:
        count = (
            await conn.execute(text("SELECT COUNT(*) FROM projects WHERE org_id='demo-org'"))
        ).scalar_one()

    assert count == 1

    await factory.dispose()
