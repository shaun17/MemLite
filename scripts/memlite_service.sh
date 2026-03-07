#!/usr/bin/env bash
set -euo pipefail

# MemLite service manager (macOS LaunchAgent)
# Default runtime: 127.0.0.1:18731

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
MEMLITE_BIN="${MEMLITE_BIN:-$ROOT_DIR/.venv/bin/memlite-server}"
HOST="${MEMLITE_HOST:-127.0.0.1}"
PORT="${MEMLITE_PORT:-18731}"
SQLITE_PATH="${MEMLITE_SQLITE_PATH:-$HOME/.memlite/memlite.sqlite3}"
KUZU_PATH="${MEMLITE_KUZU_PATH:-$HOME/.memlite/kuzu}"

LABEL="ai.memlite.server"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="/tmp/memlite"
OUT_LOG="$LOG_DIR/memlite.out.log"
ERR_LOG="$LOG_DIR/memlite.err.log"

usage() {
  cat <<'EOF'
Usage:
  scripts/memlite_service.sh install [--enable]
  scripts/memlite_service.sh uninstall
  scripts/memlite_service.sh enable
  scripts/memlite_service.sh disable
  scripts/memlite_service.sh start
  scripts/memlite_service.sh stop
  scripts/memlite_service.sh restart
  scripts/memlite_service.sh status

Notes:
- install: create LaunchAgent plist; does NOT auto-enable unless --enable
- enable: load into launchctl and start at login
- start/restart: only affect runtime state, do NOT change auto-start policy
EOF
}

need_macos() {
  [[ "$(uname -s)" == "Darwin" ]] || {
    echo "[ERROR] This script currently supports macOS only (LaunchAgent)."
    exit 1
  }
}

ensure_dirs() {
  mkdir -p "$LOG_DIR"
  mkdir -p "$(dirname "$SQLITE_PATH")"
}

ensure_bins() {
  [[ -x "$MEMLITE_BIN" ]] || {
    echo "[ERROR] memlite-server not found: $MEMLITE_BIN"
    echo "Hint: cd $ROOT_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]"
    exit 1
  }
}

write_plist() {
  ensure_dirs
  ensure_bins
  cat >"$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$MEMLITE_BIN</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>MEMLITE_HOST</key>
    <string>$HOST</string>
    <key>MEMLITE_PORT</key>
    <string>$PORT</string>
    <key>MEMLITE_SQLITE_PATH</key>
    <string>$SQLITE_PATH</string>
    <key>MEMLITE_KUZU_PATH</key>
    <string>$KUZU_PATH</string>
  </dict>

  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$OUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG</string>
</dict>
</plist>
EOF
}

is_loaded() {
  launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1
}

cmd_install() {
  local enable="0"
  if [[ "${1:-}" == "--enable" ]]; then
    enable="1"
  fi
  write_plist
  echo "[OK] Installed plist: $PLIST_PATH"
  if [[ "$enable" == "1" ]]; then
    cmd_enable
  else
    echo "[INFO] Auto-start not enabled. Run: $0 enable"
  fi
}

cmd_uninstall() {
  cmd_disable || true
  if [[ -f "$PLIST_PATH" ]]; then
    rm -f "$PLIST_PATH"
    echo "[OK] Removed $PLIST_PATH"
  else
    echo "[INFO] plist not found: $PLIST_PATH"
  fi
}

cmd_enable() {
  [[ -f "$PLIST_PATH" ]] || write_plist
  if is_loaded; then
    echo "[INFO] Service already loaded"
  else
    launchctl bootstrap "gui/$UID" "$PLIST_PATH"
    echo "[OK] Enabled (loaded): $LABEL"
  fi
  cmd_start
}

cmd_disable() {
  if is_loaded; then
    launchctl bootout "gui/$UID/$LABEL"
    echo "[OK] Disabled (unloaded): $LABEL"
  else
    echo "[INFO] Service not loaded"
  fi
}

cmd_start() {
  if is_loaded; then
    launchctl kickstart -k "gui/$UID/$LABEL"
    echo "[OK] Started: $LABEL"
  else
    echo "[WARN] Service not enabled. Running one-shot in background instead."
    MEMLITE_HOST="$HOST" MEMLITE_PORT="$PORT" MEMLITE_SQLITE_PATH="$SQLITE_PATH" MEMLITE_KUZU_PATH="$KUZU_PATH" \
      nohup "$MEMLITE_BIN" >/tmp/memlite-oneshot.out 2>/tmp/memlite-oneshot.err &
    echo "[OK] Started one-shot memlite-server (not managed by launchctl)"
  fi
}

cmd_stop() {
  if is_loaded; then
    launchctl kill SIGTERM "gui/$UID/$LABEL" || true
    echo "[OK] Stop signal sent: $LABEL"
  else
    pkill -f "memlite-server" >/dev/null 2>&1 || true
    echo "[INFO] launchctl service not loaded; tried pkill memlite-server"
  fi
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

cmd_status() {
  echo "=== MemLite Service Status ==="
  echo "Label: $LABEL"
  echo "Plist: $PLIST_PATH"
  echo "Endpoint: http://$HOST:$PORT"
  echo "SQLite: $SQLITE_PATH"
  echo "Kùzu: $KUZU_PATH"
  echo "---"
  if is_loaded; then
    echo "launchctl: loaded"
    launchctl print "gui/$UID/$LABEL" | sed -n '1,80p'
  else
    echo "launchctl: not loaded"
  fi
  echo "---"
  curl -sS "http://$HOST:$PORT/health" && echo || echo "health: unavailable"
}

main() {
  need_macos
  local cmd="${1:-}"
  case "$cmd" in
    install) shift; cmd_install "${1:-}" ;;
    uninstall) cmd_uninstall ;;
    enable) cmd_enable ;;
    disable) cmd_disable ;;
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_restart ;;
    status) cmd_status ;;
    -h|--help|help|"") usage ;;
    *)
      echo "[ERROR] Unknown command: $cmd"
      usage
      exit 1
      ;;
  esac
}

main "$@"
