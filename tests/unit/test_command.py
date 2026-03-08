from __future__ import annotations

import json
from pathlib import Path

from memlite.command import build_parser, main


def _seed_openclaw_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    cfg_dir = home / ".openclaw"
    ext_dir = cfg_dir / "extensions" / "openclaw-memolite"
    ext_dir.mkdir(parents=True, exist_ok=True)

    (ext_dir / "package.json").write_text(
        json.dumps({"openclaw": {"extensions": ["./dist/index.mjs"]}}),
        encoding="utf-8",
    )

    obj = {
        "plugins": {
            "slots": {"memory": "openclaw-memolite"},
            "entries": {
                "openclaw-memolite": {
                    "enabled": True,
                    "config": {
                        "baseUrl": "http://127.0.0.1:18731",
                        "orgId": "openclaw",
                        "projectId": "openclaw",
                        "userId": "openclaw",
                        "autoCapture": True,
                        "autoRecall": True,
                        "searchThreshold": 0.5,
                        "topK": 5,
                    },
                }
            },
        }
    }
    (cfg_dir / "openclaw.json").write_text(json.dumps(obj), encoding="utf-8")
    return home


def test_parser_supports_openclaw_new_commands():
    parser = build_parser()

    status_args = parser.parse_args(["openclaw", "status"])
    doctor_args = parser.parse_args(["openclaw", "doctor"])
    uninstall_args = parser.parse_args(["openclaw", "uninstall", "--dry-run"])
    show_args = parser.parse_args(["openclaw", "configure", "show"])
    set_args = parser.parse_args(["openclaw", "configure", "set", "--base-url", "http://127.0.0.1:18731"])

    assert status_args.action == "status"
    assert doctor_args.action == "doctor"
    assert uninstall_args.dry_run is True
    assert show_args.mode == "show"
    assert set_args.mode == "set"


def test_openclaw_configure_set_and_show(monkeypatch, tmp_path: Path, capsys):
    home = _seed_openclaw_home(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: home)

    code = main(["openclaw", "configure", "set", "--base-url", "http://127.0.0.1:19999"])
    assert code == 0

    code = main(["openclaw", "configure", "show"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"baseUrl": "http://127.0.0.1:19999"' in out


def test_openclaw_uninstall_dry_run_keeps_files(monkeypatch, tmp_path: Path):
    home = _seed_openclaw_home(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: home)

    plugin_dir = home / ".openclaw" / "extensions" / "openclaw-memolite"
    config_path = home / ".openclaw" / "openclaw.json"

    code = main(["openclaw", "uninstall", "--dry-run"])
    assert code == 0
    assert plugin_dir.exists()
    obj = json.loads(config_path.read_text(encoding="utf-8"))
    assert "openclaw-memolite" in obj["plugins"]["entries"]


def test_openclaw_uninstall_removes_plugin_and_slot(monkeypatch, tmp_path: Path):
    home = _seed_openclaw_home(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: home)

    plugin_dir = home / ".openclaw" / "extensions" / "openclaw-memolite"
    config_path = home / ".openclaw" / "openclaw.json"

    code = main(["openclaw", "uninstall"])
    assert code == 0
    assert not plugin_dir.exists()

    obj = json.loads(config_path.read_text(encoding="utf-8"))
    assert "openclaw-memolite" not in obj["plugins"]["entries"]
    assert "memory" not in obj["plugins"]["slots"]
