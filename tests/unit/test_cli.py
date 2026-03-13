from pathlib import Path

import pytest

from memolite.cli import (
    build_parser,
    build_settings,
    detect_sqlite_vec,
    render_env,
    write_env_file,
)


def test_cli_parser_supports_expected_commands():
    parser = build_parser()

    args = parser.parse_args(["configure", "--output", ".env"])
    benchmark_args = parser.parse_args(["benchmark-search", "--episode-count", "5"])
    rebuild_args = parser.parse_args(["rebuild-vectors", "--target", "semantic"])
    load_test_args = parser.parse_args(["load-test", "--total-requests", "20"])

    assert args.command == "configure"
    assert args.output == Path(".env")
    assert benchmark_args.command == "benchmark-search"
    assert benchmark_args.episode_count == 5
    assert rebuild_args.command == "rebuild-vectors"
    assert rebuild_args.target == "semantic"
    assert load_test_args.command == "load-test"
    assert load_test_args.total_requests == 20


def test_render_env_contains_required_keys(tmp_path: Path):
    settings = build_settings(data_dir=tmp_path / "data")

    content = render_env(settings)

    assert "MEMOLITE_HOST=127.0.0.1" in content
    assert "MEMOLITE_SQLITE_PATH=" in content
    assert "MEMOLITE_KUZU_PATH=" in content


def test_write_env_file_rejects_overwrite(tmp_path: Path):
    output = tmp_path / ".env"
    settings = build_settings(data_dir=tmp_path / "data")
    write_env_file(output=output, settings=settings, overwrite=False)

    with pytest.raises(FileExistsError):
        write_env_file(output=output, settings=settings, overwrite=False)


def test_detect_sqlite_vec_returns_expected_exit_codes(tmp_path: Path):
    missing = detect_sqlite_vec(extension_path=tmp_path / "missing.dylib")
    available_path = tmp_path / "sqlite-vec.dylib"
    available_path.write_text("", encoding="utf-8")
    available = detect_sqlite_vec(extension_path=available_path)

    assert missing == 1
    assert available == 0
