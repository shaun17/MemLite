"""CLI tools for MemLite initialization and local setup."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from memlite.app.resources import ResourceManager
from memlite.common.config import DEFAULT_DATA_DIR, Settings, get_settings
from memlite.storage.sqlite_vec import SqliteVecExtensionLoader


def build_parser() -> argparse.ArgumentParser:
    """Build the MemLite initialization CLI."""
    parser = argparse.ArgumentParser(prog="memlite-configure")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize local MemLite data stores")
    init_parser.add_argument("--data-dir", type=Path, default=None)

    configure_parser = subparsers.add_parser(
        "configure",
        help="Generate .env configuration and local directories",
    )
    configure_parser.add_argument("--output", type=Path, default=Path(".env"))
    configure_parser.add_argument("--data-dir", type=Path, default=None)
    configure_parser.add_argument("--sqlite-vec-extension", type=Path, default=None)
    configure_parser.add_argument("--host", default="127.0.0.1")
    configure_parser.add_argument("--port", type=int, default=8080)
    configure_parser.add_argument("--overwrite", action="store_true")

    detect_parser = subparsers.add_parser(
        "detect-sqlite-vec",
        help="Check whether a sqlite-vec extension is configured and available",
    )
    detect_parser.add_argument("--extension-path", type=Path, default=None)

    sample_parser = subparsers.add_parser(
        "sample-config",
        help="Write a sample MemLite environment file",
    )
    sample_parser.add_argument("--output", type=Path, default=Path(".env.example"))
    sample_parser.add_argument("--data-dir", type=Path, default=None)
    sample_parser.add_argument("--overwrite", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the MemLite configuration CLI."""
    args = build_parser().parse_args(argv)

    if args.command == "init":
        asyncio.run(_run_init(data_dir=args.data_dir))
        return 0
    if args.command == "configure":
        configure_environment(
            output=args.output,
            data_dir=args.data_dir,
            sqlite_vec_extension=args.sqlite_vec_extension,
            host=args.host,
            port=args.port,
            overwrite=args.overwrite,
        )
        return 0
    if args.command == "detect-sqlite-vec":
        return detect_sqlite_vec(extension_path=args.extension_path)
    if args.command == "sample-config":
        write_sample_config(
            output=args.output,
            data_dir=args.data_dir,
            overwrite=args.overwrite,
        )
        return 0
    return 1


async def _run_init(*, data_dir: Path | None) -> None:
    settings = build_settings(data_dir=data_dir)
    await initialize_local_environment(settings)
    print(f"initialized data dir: {settings.data_dir}")
    print(f"sqlite: {settings.sqlite_path}")
    print(f"kuzu: {settings.kuzu_path}")


def build_settings(
    *,
    data_dir: Path | None = None,
    sqlite_vec_extension: Path | None = None,
    host: str | None = None,
    port: int | None = None,
) -> Settings:
    """Construct runtime settings for CLI operations."""
    if data_dir is None and sqlite_vec_extension is None and host is None and port is None:
        return get_settings()

    resolved_data_dir = (data_dir or DEFAULT_DATA_DIR).expanduser()
    return Settings(
        sqlite_path=resolved_data_dir / "memlite.sqlite3",
        kuzu_path=resolved_data_dir / "kuzu",
        sqlite_vec_extension_path=sqlite_vec_extension,
        host=host or "127.0.0.1",
        port=port or 8080,
    )


async def initialize_local_environment(settings: Settings) -> None:
    """Initialize local data directory and bootstrap stores."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    resources = ResourceManager.create(settings)
    try:
        await resources.initialize()
    finally:
        await resources.close()


def configure_environment(
    *,
    output: Path,
    data_dir: Path | None,
    sqlite_vec_extension: Path | None,
    host: str,
    port: int,
    overwrite: bool,
) -> None:
    """Generate an environment file and initialize its data directory."""
    settings = build_settings(
        data_dir=data_dir,
        sqlite_vec_extension=sqlite_vec_extension,
        host=host,
        port=port,
    )
    write_env_file(output=output, settings=settings, overwrite=overwrite)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    print(f"wrote configuration: {output}")


def write_sample_config(*, output: Path, data_dir: Path | None, overwrite: bool) -> None:
    """Write a sample configuration file."""
    settings = build_settings(data_dir=data_dir)
    write_env_file(output=output, settings=settings, overwrite=overwrite)
    print(f"wrote sample configuration: {output}")


def write_env_file(*, output: Path, settings: Settings, overwrite: bool) -> None:
    """Write a MemLite environment file."""
    if output.exists() and not overwrite:
        raise FileExistsError(f"file already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_env(settings), encoding="utf-8")


def render_env(settings: Settings) -> str:
    """Render an environment file from settings."""
    lines = [
        f"MEMLITE_HOST={settings.host}",
        f"MEMLITE_PORT={settings.port}",
        f"MEMLITE_SQLITE_PATH={settings.sqlite_path}",
        f"MEMLITE_KUZU_PATH={settings.kuzu_path}",
    ]
    if settings.sqlite_vec_extension_path is not None:
        lines.append(
            f"MEMLITE_SQLITE_VEC_EXTENSION_PATH={settings.sqlite_vec_extension_path}"
        )
    return "\n".join(lines) + "\n"


def detect_sqlite_vec(*, extension_path: Path | None) -> int:
    """Return a shell-style exit code for sqlite-vec availability."""
    settings = build_settings(sqlite_vec_extension=extension_path)
    loader = SqliteVecExtensionLoader(settings)
    if loader.is_available():
        print(f"sqlite-vec available: {loader.detect_extension()}")
        return 0
    configured = settings.sqlite_vec_extension_path
    if configured is None:
        print("sqlite-vec not configured")
    else:
        print(f"sqlite-vec missing: {configured}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
