from pathlib import Path

import pytest

from memlite.common.config import Settings
from memlite.storage.sqlite_engine import SqliteEngineFactory
from memlite.storage.sqlite_vec import SqliteVecExtensionLoader, SqliteVecIndex


@pytest.mark.anyio
async def test_extension_loader_detects_missing_or_present_extension(tmp_path: Path):
    missing = Settings(sqlite_vec_extension_path=tmp_path / "missing.dylib")
    present_path = tmp_path / "vec.dylib"
    present_path.write_text("stub")
    present = Settings(sqlite_vec_extension_path=present_path)

    assert SqliteVecExtensionLoader(missing).is_available() is False
    assert SqliteVecExtensionLoader(present).is_available() is True


@pytest.mark.anyio
async def test_sqlite_vec_index_supports_init_batch_and_search(tmp_path: Path):
    factory = SqliteEngineFactory(Settings(sqlite_path=tmp_path / "memlite.sqlite3"))
    await factory.initialize_schema()
    index = SqliteVecIndex(factory, "test_feature_vectors")
    await index.initialize()
    await index.batch_upsert(
        [
            (1, [1.0, 0.0]),
            (2, [0.0, 1.0]),
            (3, [0.8, 0.2]),
        ]
    )

    results = await index.search_top_k([1.0, 0.0], limit=2)

    assert [result.item_id for result in results] == [1, 3]

    await factory.dispose()
