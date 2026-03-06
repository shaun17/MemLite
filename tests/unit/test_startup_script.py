from pathlib import Path


def test_start_local_script_exists():
    script = Path(__file__).resolve().parents[2] / "scripts" / "start_local.sh"

    assert script.exists()
    assert script.read_text().startswith("#!/usr/bin/env bash")
