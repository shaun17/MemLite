from pathlib import Path

import pytest

from memlite.cli import configure_environment, initialize_local_environment, write_sample_config
from memlite.common.config import Settings


@pytest.mark.anyio
async def test_cli_init_bootstraps_sqlite_and_kuzu(tmp_path: Path):
    data_dir = tmp_path / "memlite-data"
    settings = Settings(
        sqlite_path=data_dir / "memlite.sqlite3",
        kuzu_path=data_dir / "kuzu",
    )

    await initialize_local_environment(settings)

    assert settings.sqlite_path.exists()
    assert data_dir.exists()


def test_cli_configure_writes_env_and_creates_data_dir(tmp_path: Path):
    output = tmp_path / ".env"
    data_dir = tmp_path / "runtime"

    configure_environment(
        output=output,
        data_dir=data_dir,
        sqlite_vec_extension=None,
        host="127.0.0.1",
        port=9090,
        overwrite=True,
    )

    content = output.read_text(encoding="utf-8")
    assert "MEMLITE_PORT=9090" in content
    assert data_dir.exists()


def test_cli_sample_config_generates_template_file(tmp_path: Path):
    output = tmp_path / ".env.example"

    write_sample_config(output=output, data_dir=tmp_path / "data", overwrite=True)

    content = output.read_text(encoding="utf-8")
    assert "MEMLITE_SQLITE_PATH=" in content
    assert "MEMLITE_KUZU_PATH=" in content
