from pathlib import Path

import pytest

from memolite.common.config import Settings
from memolite.storage.kuzu_engine import KuzuEngineFactory


@pytest.mark.anyio
async def test_kuzu_engine_initializes_data_dir_schema_and_queries(tmp_path: Path):
    factory = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "kuzu-db"))

    data_dir = await factory.initialize_data_dir()
    await factory.initialize_schema()
    await factory.execute("CREATE (:Episode {uid: 'ep-1', session_id: 's1'})")
    rows = await factory.query("MATCH (e:Episode) RETURN e.uid ORDER BY e.uid")

    assert data_dir.exists()
    assert rows == [["ep-1"]]

    await factory.close()


@pytest.mark.anyio
async def test_kuzu_engine_reuses_connection_and_database(tmp_path: Path):
    factory = KuzuEngineFactory(Settings(kuzu_path=tmp_path / "kuzu-db"))

    database_one = await factory.create_database()
    database_two = await factory.create_database()
    connection_one = await factory.create_connection()
    connection_two = await factory.create_connection()

    assert database_one is database_two
    assert connection_one is connection_two

    await factory.close()
