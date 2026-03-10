#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"
EXPECTED_PLUGIN_ID="${EXPECTED_PLUGIN_ID:-openclaw-memolite}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERROR] missing command: $1"
    exit 1
  }
}

pass() {
  echo "[PASS] $*"
}

fail() {
  echo "[FAIL] $*"
  exit 1
}

need_cmd openclaw
need_cmd python3
need_cmd curl

[[ -f "$OPENCLAW_CONFIG" ]] || fail "missing OpenClaw config: $OPENCLAW_CONFIG"

if [[ -z "${BASE_URL:-}" ]]; then
  BASE_URL="$(
    python3 - <<PY
import json
from pathlib import Path

config = json.loads(Path("$OPENCLAW_CONFIG").read_text())
value = (
    config.get("plugins", {})
    .get("entries", {})
    .get("$EXPECTED_PLUGIN_ID", {})
    .get("config", {})
    .get("baseUrl")
)
print(value or "http://127.0.0.1:8080")
PY
  )"
fi

echo "[1/4] checking plugin registry"
plugins_list="$(openclaw plugins list || true)"
echo "$plugins_list"
if python3 - <<PY
import json
from pathlib import Path

config = json.loads(Path("$OPENCLAW_CONFIG").read_text())
installs = config.get("plugins", {}).get("installs", {})
entry = installs.get("$EXPECTED_PLUGIN_ID")
if not entry:
    raise SystemExit(1)
print(f"sourcePath={entry.get('sourcePath')}")
print(f"installPath={entry.get('installPath')}")
PY
then
  pass "plugin install record exists"
else
  fail "plugin $EXPECTED_PLUGIN_ID has no install record in $OPENCLAW_CONFIG"
fi

echo "[2/4] checking memory slot binding"
if python3 - <<PY
import json
from pathlib import Path

config = json.loads(Path("$OPENCLAW_CONFIG").read_text())
plugin_id = config.get("plugins", {}).get("slots", {}).get("memory")
enabled = config.get("plugins", {}).get("entries", {}).get("$EXPECTED_PLUGIN_ID", {}).get("enabled")
base_url = config.get("plugins", {}).get("entries", {}).get("$EXPECTED_PLUGIN_ID", {}).get("config", {}).get("baseUrl")
print(f"memory_slot={plugin_id}")
print(f"enabled={enabled}")
print(f"baseUrl={base_url}")
if plugin_id != "$EXPECTED_PLUGIN_ID":
    raise SystemExit(1)
if enabled is not True:
    raise SystemExit(2)
PY
then
  pass "memory slot is bound to $EXPECTED_PLUGIN_ID and enabled"
else
  fail "OpenClaw config does not bind and enable $EXPECTED_PLUGIN_ID"
fi

echo "[3/4] checking MemoLite backend health"
health="$(curl -fsS "$BASE_URL/health")" || fail "cannot reach $BASE_URL/health"
echo "$health"
echo "$health" | grep -q '"status"' || fail "unexpected health payload: $health"
pass "backend health endpoint is reachable"

echo "[4/4] next runtime proof"
cat <<EOF
Run these inside OpenClaw:
  1. memolite_status
  2. memolite_search {"query":"我喜欢吃什么","scope":"all"}
  3. memolite_get {"id":"<uid from previous step>"}

Success criteria:
  - every response includes provider="memolite"
  - every response includes pluginId="openclaw-memolite"
  - every response includes executed=true
EOF

pass "static verification completed"
