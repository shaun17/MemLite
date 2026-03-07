"""Unified memoLite command entrypoint.

This command wraps common workflows:
- memolite serve
- memolite init/configure/... (delegates to memolite-configure)
- memolite service ...
- memolite openclaw setup
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from memlite.app.main import main as run_server
from memlite.cli import main as configure_main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_script(script: str, args: list[str], env: dict[str, str] | None = None) -> int:
    script_path = _repo_root() / "scripts" / script
    if not script_path.exists():
        raise FileNotFoundError(f"script not found: {script_path}")
    cmd = [str(script_path), *args]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, env=merged_env)
    return int(proc.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memolite")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="Run MemLite API server in foreground")

    # Keep compatibility for existing configure workflow.
    config = sub.add_parser("configure", help="Run memolite-configure subcommands")
    config.add_argument("args", nargs=argparse.REMAINDER)

    service = sub.add_parser("service", help="Manage managed MemLite service")
    service_sub = service.add_subparsers(dest="action", required=True)
    install = service_sub.add_parser("install", help="Install service definition")
    install.add_argument("--enable", action="store_true", help="Enable auto-start after install")
    service_sub.add_parser("uninstall")
    service_sub.add_parser("enable")
    service_sub.add_parser("disable")
    service_sub.add_parser("start")
    service_sub.add_parser("stop")
    service_sub.add_parser("restart")
    service_sub.add_parser("status")

    openclaw = sub.add_parser("openclaw", help="OpenClaw integration commands")
    oc_sub = openclaw.add_subparsers(dest="action", required=True)
    setup = oc_sub.add_parser("setup", help="One-shot OpenClaw+MemLite setup")
    setup.add_argument("--base-url", default="http://127.0.0.1:18731")
    setup.add_argument("--org-id", default="openclaw")
    setup.add_argument("--project-id", default="openclaw")
    setup.add_argument("--user-id", default="openclaw")
    setup.add_argument("--auto-capture", choices=["true", "false"], default="true")
    setup.add_argument("--auto-recall", choices=["true", "false"], default="true")
    setup.add_argument("--search-threshold", type=float, default=0.5)
    setup.add_argument("--top-k", type=int, default=5)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        run_server()
        return 0

    if args.command == "configure":
        forwarded = args.args
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]
        return configure_main(forwarded)

    if args.command == "service":
        cmd_args: list[str] = [args.action]
        if args.action == "install" and args.enable:
            cmd_args.append("--enable")
        return _run_script("memlite_service.sh", cmd_args)

    if args.command == "openclaw" and args.action == "setup":
        env = {
            "BASE_URL": args.base_url,
            "ORG_ID": args.org_id,
            "PROJECT_ID": args.project_id,
            "USER_ID": args.user_id,
            "AUTO_CAPTURE": args.auto_capture,
            "AUTO_RECALL": args.auto_recall,
            "SEARCH_THRESHOLD": str(args.search_threshold),
            "TOP_K": str(args.top_k),
        }
        return _run_script("setup_openclaw_memlite.sh", [], env=env)

    return 1


if __name__ == "__main__":
    sys.exit(main())
