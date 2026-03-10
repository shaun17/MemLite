#!/usr/bin/env bash
set -euo pipefail

# One-shot setup:
# 1) install OpenClaw memolite plugin
# 2) configure plugin entry in ~/.openclaw/openclaw.json
# 3) install/start memolite service (LaunchAgent)
# 4) restart openclaw gateway
# 5) health checks

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_PATH="${PLUGIN_PATH:-$ROOT_DIR/integrations/openclaw}"
BASE_URL="${BASE_URL:-http://127.0.0.1:18731}"
ORG_ID="${ORG_ID:-openclaw}"
PROJECT_ID="${PROJECT_ID:-openclaw}"
USER_ID="${USER_ID:-openclaw}"
AUTO_CAPTURE="${AUTO_CAPTURE:-true}"
AUTO_RECALL="${AUTO_RECALL:-true}"
SEARCH_THRESHOLD="${SEARCH_THRESHOLD:-0.5}"
TOP_K="${TOP_K:-5}"

OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERROR] missing command: $1"
    exit 1
  }
}

need_cmd openclaw
need_cmd python3

echo "[1/5] Install plugin: $PLUGIN_PATH"
openclaw plugins install "$PLUGIN_PATH"

echo "[2/5] Update OpenClaw config"
python3 - <<PY
import json, pathlib
p=pathlib.Path("$OPENCLAW_CONFIG")
obj=json.loads(p.read_text())
plugins=obj.setdefault('plugins',{})
plugins.setdefault('slots',{})['memory']='openclaw-memolite'
entries=plugins.setdefault('entries',{})
entry=entries.setdefault('openclaw-memolite',{})
entry['enabled']=True
entry['config']={
  'baseUrl':'$BASE_URL',
  'orgId':'$ORG_ID',
  'projectId':'$PROJECT_ID',
  'userId':'$USER_ID',
  'autoCapture': '$AUTO_CAPTURE'.lower()=='true',
  'autoRecall': '$AUTO_RECALL'.lower()=='true',
  'searchThreshold': float('$SEARCH_THRESHOLD'),
  'topK': int('$TOP_K')
}
p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
print('updated', p)
PY

echo "[3/5] Install and enable memolite service"
MEMOLITE_PORT="${BASE_URL##*:}" MEMLITE_PORT="${BASE_URL##*:}" "$ROOT_DIR/scripts/memolite_service.sh" install --enable

echo "[4/5] Restart OpenClaw gateway"
openclaw gateway restart

echo "[5/5] Health checks"
echo "- memolite health: $BASE_URL/health"
curl -sS "$BASE_URL/health" && echo
openclaw plugins list | rg -n "openclaw-memolite|memory-core|memory-lancedb|Plugins" -n

echo
echo "[OK] setup completed"
