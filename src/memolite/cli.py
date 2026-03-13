"""CLI tools for MemLite initialization and local setup."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from memolite.app.resources import ResourceManager
from memolite.common.config import DEFAULT_DATA_DIR, Settings, get_settings
from memolite.storage.sqlite_vec import SqliteVecExtensionLoader
from memolite.tools.migration import (
    export_snapshot,
    import_snapshot,
    reconcile_snapshot,
    rebuild_vectors_snapshot,
    repair_snapshot,
)
from memolite.tools.benchmark import benchmark_search_workload
from memolite.tools.loadtest import load_test_memory_search


def build_parser() -> argparse.ArgumentParser:
    """Build the MemLite initialization CLI."""
    parser = argparse.ArgumentParser(prog="memolite-configure")
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
    configure_parser.add_argument("--port", type=int, default=18731)
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

    export_parser = subparsers.add_parser("export", help="Export a MemLite snapshot to JSON")
    export_parser.add_argument("--output", type=Path, required=True)
    export_parser.add_argument("--data-dir", type=Path, default=None)

    import_parser = subparsers.add_parser("import", help="Import a MemLite snapshot from JSON")
    import_parser.add_argument("--input", type=Path, required=True)
    import_parser.add_argument("--data-dir", type=Path, default=None)

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Reconcile SQLite, sqlite-vec and Kùzu state",
    )
    reconcile_parser.add_argument("--output", type=Path, default=None)
    reconcile_parser.add_argument("--data-dir", type=Path, default=None)

    repair_parser = subparsers.add_parser(
        "repair",
        help="Repair derivative graph/vector state from SQLite truth",
    )
    repair_parser.add_argument("--output", type=Path, default=None)
    repair_parser.add_argument("--data-dir", type=Path, default=None)

    rebuild_vectors_parser = subparsers.add_parser(
        "rebuild-vectors",
        help="Rebuild semantic and/or derivative vectors from persisted source data",
    )
    rebuild_vectors_parser.add_argument(
        "--target",
        choices=["semantic", "derivative", "all"],
        default="all",
    )
    rebuild_vectors_parser.add_argument("--output", type=Path, default=None)
    rebuild_vectors_parser.add_argument("--data-dir", type=Path, default=None)

    benchmark_parser = subparsers.add_parser(
        "benchmark-search",
        help="Run a local search benchmark against episodic and semantic paths",
    )
    benchmark_parser.add_argument("--output", type=Path, default=None)
    benchmark_parser.add_argument("--data-dir", type=Path, default=None)
    benchmark_parser.add_argument("--episode-count", type=int, default=25)
    benchmark_parser.add_argument("--query-iterations", type=int, default=10)

    load_test_parser = subparsers.add_parser(
        "load-test",
        help="Run concurrent HTTP load against the memory search API",
    )
    load_test_parser.add_argument("--base-url", default="http://127.0.0.1:18731")
    load_test_parser.add_argument("--org-id", default="demo-org")
    load_test_parser.add_argument("--project-id", default="demo-project")
    load_test_parser.add_argument("--query", default="memory recall")
    load_test_parser.add_argument("--total-requests", type=int, default=100)
    load_test_parser.add_argument("--concurrency", type=int, default=10)
    load_test_parser.add_argument("--timeout-seconds", type=float, default=5.0)
    load_test_parser.add_argument("--output", type=Path, default=None)

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
    if args.command == "export":
        asyncio.run(_run_export(output=args.output, data_dir=args.data_dir))
        return 0
    if args.command == "import":
        asyncio.run(_run_import(input_path=args.input, data_dir=args.data_dir))
        return 0
    if args.command == "reconcile":
        asyncio.run(_run_reconcile(output=args.output, data_dir=args.data_dir))
        return 0
    if args.command == "repair":
        asyncio.run(_run_repair(output=args.output, data_dir=args.data_dir))
        return 0
    if args.command == "rebuild-vectors":
        asyncio.run(
            _run_rebuild_vectors(
                target=args.target,
                output=args.output,
                data_dir=args.data_dir,
            )
        )
        return 0
    if args.command == "benchmark-search":
        asyncio.run(
            _run_benchmark_search(
                output=args.output,
                data_dir=args.data_dir,
                episode_count=args.episode_count,
                query_iterations=args.query_iterations,
            )
        )
        return 0
    if args.command == "load-test":
        asyncio.run(
            _run_load_test(
                base_url=args.base_url,
                org_id=args.org_id,
                project_id=args.project_id,
                query=args.query,
                total_requests=args.total_requests,
                concurrency=args.concurrency,
                timeout_seconds=args.timeout_seconds,
                output=args.output,
            )
        )
        return 0
    return 1


async def _run_init(*, data_dir: Path | None) -> None:
    settings = build_settings(data_dir=data_dir)
    await initialize_local_environment(settings)
    print(f"initialized data dir: {settings.data_dir}")
    print(f"sqlite: {settings.sqlite_path}")
    print(f"kuzu: {settings.kuzu_path}")


async def _run_export(*, output: Path, data_dir: Path | None) -> None:
    settings = build_settings(data_dir=data_dir)
    written = await export_snapshot(settings, output)
    print(f"exported snapshot: {written}")


async def _run_import(*, input_path: Path, data_dir: Path | None) -> None:
    settings = build_settings(data_dir=data_dir)
    await import_snapshot(settings, input_path)
    print(f"imported snapshot: {input_path}")


async def _run_reconcile(*, output: Path | None, data_dir: Path | None) -> None:
    settings = build_settings(data_dir=data_dir)
    result = await reconcile_snapshot(settings)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_dump(result), encoding="utf-8")
        print(f"wrote reconcile report: {output}")
        return
    print(json_dump(result))


async def _run_repair(*, output: Path | None, data_dir: Path | None) -> None:
    settings = build_settings(data_dir=data_dir)
    result = await repair_snapshot(settings)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_dump(result), encoding="utf-8")
        print(f"wrote repair report: {output}")
        return
    print(json_dump(result))


async def _run_rebuild_vectors(
    *,
    target: str,
    output: Path | None,
    data_dir: Path | None,
) -> None:
    settings = build_settings(data_dir=data_dir)
    result = await rebuild_vectors_snapshot(settings, target=target)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_dump(result), encoding="utf-8")
        print(f"wrote rebuild-vectors report: {output}")
        return
    print(json_dump(result))


async def _run_benchmark_search(
    *,
    output: Path | None,
    data_dir: Path | None,
    episode_count: int,
    query_iterations: int,
) -> None:
    settings = build_settings(data_dir=data_dir)
    result = await benchmark_search_workload(
        settings=settings,
        episode_count=episode_count,
        query_iterations=query_iterations,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_dump(result), encoding="utf-8")
        print(f"wrote benchmark report: {output}")
        return
    print(json_dump(result))


async def _run_load_test(
    *,
    base_url: str,
    org_id: str,
    project_id: str,
    query: str,
    total_requests: int,
    concurrency: int,
    timeout_seconds: float,
    output: Path | None,
) -> None:
    result = await load_test_memory_search(
        base_url=base_url,
        org_id=org_id,
        project_id=project_id,
        query=query,
        total_requests=total_requests,
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_dump(result), encoding="utf-8")
        print(f"wrote load test report: {output}")
        return
    print(json_dump(result))


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
        sqlite_path=resolved_data_dir / "memolite.sqlite3",
        kuzu_path=resolved_data_dir / "kuzu",
        sqlite_vec_extension_path=sqlite_vec_extension,
        host=host or "127.0.0.1",
        port=port or 18731,
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
        f"MEMOLITE_HOST={settings.host}",
        f"MEMOLITE_PORT={settings.port}",
        f"MEMOLITE_SQLITE_PATH={settings.sqlite_path}",
        f"MEMOLITE_KUZU_PATH={settings.kuzu_path}",
    ]
    if settings.sqlite_vec_extension_path is not None:
        lines.append(
            f"MEMOLITE_SQLITE_VEC_EXTENSION_PATH={settings.sqlite_vec_extension_path}"
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


def json_dump(payload: object) -> str:
    """Serialize a CLI result payload."""
    import json

    return json.dumps(payload, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
