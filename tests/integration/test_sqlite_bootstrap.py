from pathlib import Path

import pytest
from sqlalchemy import text

from memolite.common.config import Settings
from memolite.storage.sqlite_engine import SqliteEngineFactory


@pytest.mark.anyio
async def test_sqlite_bootstrap_supports_multiple_operations(tmp_path: Path):
    sqlite_path = tmp_path / "memolite.sqlite3"
    factory = SqliteEngineFactory(Settings(sqlite_path=sqlite_path))
    await factory.initialize_schema()

    session_factory = factory.create_session_factory()
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO sessions (session_key, org_id, project_id, session_id) VALUES ('org/proj/s1', 'org', 'proj', 's1')"
            )
        )
        await session.execute(
            text(
                "INSERT INTO episodes (uid, session_key, session_id, producer_id, producer_role, content, content_type, episode_type) VALUES ('e1', 'org/proj/s1', 's1', 'u1', 'user', 'hello', 'string', 'message')"
            )
        )
        await session.commit()

    engine = factory.create_engine()
    async with engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM episodes"))).scalar_one()

    assert count == 1

    await factory.dispose()
