"""Unified memoLite command entrypoint.

This command wraps common workflows:
- memolite serve
- memolite init/configure/... (delegates to memolite-configure)
- memolite service ...
- memolite openclaw ...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from importlib import resources
from pathlib import Path

from memlite.app.main import main as run_server
from memlite.cli import main as configure_main

PLUGIN_ID = "openclaw-memolite"
DEFAULT_BASE_URL = "http://127.0.0.1:18731"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_script_path(script: str) -> Path:
    bundled = resources.files("memlite").joinpath("scripts", script)
    if bundled.is_file():
        return Path(str(bundled))
    fallback = _repo_root() / "scripts" / script
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"script not found: {script}")


def _run_script(script: str, args: list[str], env: dict[str, str] | None = None) -> int:
    script_path = _resolve_script_path(script)
    cmd = ["bash", str(script_path), *args]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, env=merged_env)
    return int(proc.returncode)


def _openclaw_config_path() -> Path:
    return Path.home() / ".openclaw" / "openclaw.json"


def _openclaw_plugin_dir() -> Path:
    return Path.home() / ".openclaw" / "extensions" / PLUGIN_ID


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _entry_config(obj: dict) -> dict:
    return obj.get("plugins", {}).get("entries", {}).get(PLUGIN_ID, {}).get("config", {})


def _check_health(base_url: str) -> tuple[bool, str]:
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=2.5) as resp:
            payload = resp.read().decode("utf-8", errors="replace").strip()
            return resp.status == 200, payload
    except urllib.error.URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:  # pragma: no cover - defensive
        return False, str(exc)


def _print_status(config_path: Path, obj: dict) -> int:
    plugin_dir = _openclaw_plugin_dir()
    entry = obj.get("plugins", {}).get("entries", {}).get(PLUGIN_ID, {})
    config = entry.get("config", {})
    slot = obj.get("plugins", {}).get("slots", {}).get("memory")

    base_url = config.get("baseUrl", DEFAULT_BASE_URL)
    health_ok, health_detail = _check_health(base_url)

    print("=== memolite openclaw status ===")
    print(f"config_path: {config_path}")
    print(f"plugin_dir_exists: {plugin_dir.exists()}")
    print(f"plugin_entry_enabled: {bool(entry.get('enabled', False))}")
    print(f"memory_slot: {slot}")
    print(f"base_url: {base_url}")
    print(f"health_ok: {health_ok}")
    print(f"health_detail: {health_detail}")

    has_minimum = plugin_dir.exists() and bool(entry) and slot == PLUGIN_ID
    return 0 if has_minimum and health_ok else 1


def _openclaw_status() -> int:
    config_path = _openclaw_config_path()
    if not config_path.exists():
        print(f"[ERROR] openclaw config missing: {config_path}")
        return 1
    obj = _load_json(config_path)
    return _print_status(config_path, obj)


def _openclaw_doctor() -> int:
    issues: list[str] = []
    config_path = _openclaw_config_path()
    plugin_dir = _openclaw_plugin_dir()

    if shutil.which("openclaw") is None:
        issues.append("missing openclaw command (install OpenClaw CLI first)")

    if not config_path.exists():
        issues.append(f"missing config: {config_path}")
        obj: dict = {}
    else:
        obj = _load_json(config_path)

    entry = obj.get("plugins", {}).get("entries", {}).get(PLUGIN_ID, {})
    slots = obj.get("plugins", {}).get("slots", {})

    if slots.get("memory") != PLUGIN_ID:
        issues.append("plugins.slots.memory is not openclaw-memolite")

    if not entry:
        issues.append("plugins.entries.openclaw-memolite is missing")

    if entry and not bool(entry.get("enabled", False)):
        issues.append("plugins.entries.openclaw-memolite.enabled is false")

    config = entry.get("config", {}) if entry else {}
    base_url = config.get("baseUrl", DEFAULT_BASE_URL)
    if ":18731" not in base_url:
        issues.append(f"baseUrl not using default 18731: {base_url}")

    health_ok, health_detail = _check_health(base_url)
    if not health_ok:
        issues.append(f"memolite health check failed: {health_detail}")

    if not plugin_dir.exists():
        issues.append(f"plugin dir missing: {plugin_dir}")

    package_json = plugin_dir / "package.json"
    if package_json.exists():
        try:
            pkg = _load_json(package_json)
            ext = pkg.get("openclaw", {}).get("extensions")
            if not ext:
                issues.append("plugin package.json missing openclaw.extensions")
        except Exception as exc:
            issues.append(f"invalid plugin package.json: {exc}")
    else:
        issues.append(f"plugin package missing: {package_json}")

    for candidate in ("memory-core", "memory-lancedb"):
        candidate_entry = obj.get("plugins", {}).get("entries", {}).get(candidate, {})
        if candidate_entry.get("enabled"):
            issues.append(f"conflict: {candidate} enabled (recommend disabling)")

    print("=== memolite openclaw doctor ===")
    print(f"config_path: {config_path}")
    print(f"plugin_dir: {plugin_dir}")
    print(f"base_url: {base_url}")

    if not issues:
        print("[OK] all checks passed")
        return 0

    print("[WARN] issues detected:")
    for idx, issue in enumerate(issues, start=1):
        print(f"  {idx}. {issue}")

    print("\nSuggested fixes:")
    print("- memolite openclaw setup")
    print(f"- memolite openclaw configure set --base-url {DEFAULT_BASE_URL}")
    print("- memolite service install --enable")
    print("- memolite service status")
    return 1


def _openclaw_uninstall(dry_run: bool) -> int:
    config_path = _openclaw_config_path()
    plugin_dir = _openclaw_plugin_dir()

    print("=== memolite openclaw uninstall ===")
    if dry_run:
        print("[DRY-RUN] no filesystem changes will be made")

    if config_path.exists():
        obj = _load_json(config_path)
        plugins = obj.setdefault("plugins", {})
        entries = plugins.setdefault("entries", {})
        slots = plugins.setdefault("slots", {})

        changed = False
        if PLUGIN_ID in entries:
            changed = True
            print(f"- remove plugins.entries.{PLUGIN_ID}")
            if not dry_run:
                entries.pop(PLUGIN_ID, None)
        if slots.get("memory") == PLUGIN_ID:
            changed = True
            print("- clear plugins.slots.memory")
            if not dry_run:
                slots.pop("memory", None)

        if changed and not dry_run:
            _save_json(config_path, obj)
            print(f"[OK] updated {config_path}")
        elif not changed:
            print("[INFO] no memolite plugin config found")
    else:
        print(f"[INFO] config not found: {config_path}")

    if plugin_dir.exists():
        print(f"- remove plugin dir: {plugin_dir}")
        if not dry_run:
            shutil.rmtree(plugin_dir)
            print("[OK] plugin dir removed")
    else:
        print(f"[INFO] plugin dir not found: {plugin_dir}")

    return 0


def _openclaw_configure_show() -> int:
    config_path = _openclaw_config_path()
    if not config_path.exists():
        print(f"[ERROR] openclaw config missing: {config_path}")
        return 1

    obj = _load_json(config_path)
    entry = obj.get("plugins", {}).get("entries", {}).get(PLUGIN_ID, {})
    print(json.dumps(entry.get("config", {}), ensure_ascii=False, indent=2))
    return 0


def _openclaw_configure_set(base_url: str) -> int:
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        print(f"[ERROR] invalid base url: {base_url}")
        return 1

    config_path = _openclaw_config_path()
    if not config_path.exists():
        print(f"[ERROR] openclaw config missing: {config_path}")
        return 1

    obj = _load_json(config_path)
    plugins = obj.setdefault("plugins", {})
    entries = plugins.setdefault("entries", {})
    slots = plugins.setdefault("slots", {})
    slots["memory"] = PLUGIN_ID

    entry = entries.setdefault(PLUGIN_ID, {})
    entry["enabled"] = True
    cfg = entry.setdefault("config", {})
    cfg["baseUrl"] = base_url
    cfg.setdefault("orgId", "openclaw")
    cfg.setdefault("projectId", "openclaw")
    cfg.setdefault("userId", "openclaw")
    cfg.setdefault("autoCapture", True)
    cfg.setdefault("autoRecall", True)
    cfg.setdefault("searchThreshold", 0.5)
    cfg.setdefault("topK", 5)

    _save_json(config_path, obj)
    print(f"[OK] updated baseUrl -> {base_url}")
    return 0


def _openclaw_configure_reset() -> int:
    return _openclaw_configure_set(DEFAULT_BASE_URL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memolite")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="Run memoLite API server in foreground")

    # Keep compatibility for existing configure workflow.
    config = sub.add_parser("configure", help="Run memolite-configure subcommands")
    config.add_argument("args", nargs=argparse.REMAINDER)

    service = sub.add_parser("service", help="Manage managed memoLite service")
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

    setup = oc_sub.add_parser("setup", help="One-shot OpenClaw+memoLite setup")
    setup.add_argument("--base-url", default=DEFAULT_BASE_URL)
    setup.add_argument("--org-id", default="openclaw")
    setup.add_argument("--project-id", default="openclaw")
    setup.add_argument("--user-id", default="openclaw")
    setup.add_argument("--auto-capture", choices=["true", "false"], default="true")
    setup.add_argument("--auto-recall", choices=["true", "false"], default="true")
    setup.add_argument("--search-threshold", type=float, default=0.5)
    setup.add_argument("--top-k", type=int, default=5)

    oc_sub.add_parser("status", help="Check OpenClaw memolite integration status")
    oc_sub.add_parser("doctor", help="Diagnose OpenClaw memolite integration")

    uninstall = oc_sub.add_parser("uninstall", help="Remove OpenClaw memolite integration")
    uninstall.add_argument("--dry-run", action="store_true", help="Preview changes without applying")

    configure = oc_sub.add_parser("configure", help="Show/update OpenClaw memolite config")
    configure_sub = configure.add_subparsers(dest="mode", required=True)
    configure_sub.add_parser("show", help="Show current memolite plugin config")
    set_cmd = configure_sub.add_parser("set", help="Set memolite plugin config fields")
    set_cmd.add_argument("--base-url", required=True, help="Base URL, e.g. http://127.0.0.1:18731")
    configure_sub.add_parser("reset", help="Reset to default config values")

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
        return _run_script("memolite_service.sh", cmd_args)

    if args.command == "openclaw":
        if args.action == "setup":
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
            bundled_plugin = resources.files("memlite").joinpath("integrations", "openclaw")
            if bundled_plugin.is_dir() and "PLUGIN_PATH" not in env and "PLUGIN_PATH" not in os.environ:
                env["PLUGIN_PATH"] = str(bundled_plugin)
            return _run_script("setup_openclaw_memolite.sh", [], env=env)
        if args.action == "status":
            return _openclaw_status()
        if args.action == "doctor":
            return _openclaw_doctor()
        if args.action == "uninstall":
            return _openclaw_uninstall(dry_run=args.dry_run)
        if args.action == "configure":
            if args.mode == "show":
                return _openclaw_configure_show()
            if args.mode == "set":
                return _openclaw_configure_set(args.base_url)
            if args.mode == "reset":
                return _openclaw_configure_reset()

    return 1


if __name__ == "__main__":
    sys.exit(main())
