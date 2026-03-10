#!/usr/bin/env bash
set -euo pipefail

# memoLite service manager (macOS LaunchAgent)
# Default runtime: 127.0.0.1:18731

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${MEMOLITE_ENV_FILE:-${MEMLITE_ENV_FILE:-$ROOT_DIR/.env}}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

DEFAULT_MEMOLITE_BIN="$(command -v memolite-server || true)"
if [[ -z "$DEFAULT_MEMOLITE_BIN" && -x "$HOME/.local/bin/memolite-server" ]]; then
  DEFAULT_MEMOLITE_BIN="$HOME/.local/bin/memolite-server"
fi
if [[ -z "$DEFAULT_MEMOLITE_BIN" && -x "$ROOT_DIR/.venv/bin/memolite-server" ]]; then
  DEFAULT_MEMOLITE_BIN="$ROOT_DIR/.venv/bin/memolite-server"
fi
MEMOLITE_BIN="${MEMOLITE_BIN:-${MEMLITE_BIN:-$DEFAULT_MEMOLITE_BIN}}"
HOST="${MEMOLITE_HOST:-${MEMLITE_HOST:-127.0.0.1}}"
PORT="${MEMOLITE_PORT:-${MEMLITE_PORT:-18731}}"
SQLITE_PATH="${MEMOLITE_SQLITE_PATH:-${MEMLITE_SQLITE_PATH:-$HOME/.memolite/memolite.sqlite3}}"
KUZU_PATH="${MEMOLITE_KUZU_PATH:-${MEMLITE_KUZU_PATH:-$HOME/.memolite/kuzu}}"

LABEL="ai.memolite.server"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="/tmp/memolite"
OUT_LOG="$LOG_DIR/memolite.out.log"
ERR_LOG="$LOG_DIR/memolite.err.log"

usage() {
  cat <<'EOF'
Usage:
  scripts/memolite_service.sh install [--enable]
  scripts/memolite_service.sh uninstall
  scripts/memolite_service.sh enable
  scripts/memolite_service.sh disable
  scripts/memolite_service.sh start
  scripts/memolite_service.sh stop
  scripts/memolite_service.sh restart
  scripts/memolite_service.sh status

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
  [[ -n "$MEMOLITE_BIN" && -x "$MEMOLITE_BIN" ]] || {
    echo "[ERROR] memolite-server not found."
    echo "Checked: ${MEMOLITE_BIN:-<empty>}"
    echo "Hint: ensure memolite is installed (pipx install memolite), or set MEMOLITE_BIN explicitly."
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
    <string>$MEMOLITE_BIN</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>MEMOLITE_HOST</key>
    <string>$HOST</string>
    <key>MEMOLITE_PORT</key>
    <string>$PORT</string>
    <key>MEMOLITE_SQLITE_PATH</key>
    <string>$SQLITE_PATH</string>
    <key>MEMOLITE_KUZU_PATH</key>
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
    MEMOLITE_HOST="$HOST" MEMOLITE_PORT="$PORT" MEMOLITE_SQLITE_PATH="$SQLITE_PATH" MEMOLITE_KUZU_PATH="$KUZU_PATH" \
      nohup "$MEMOLITE_BIN" >/tmp/memolite-oneshot.out 2>/tmp/memolite-oneshot.err &
    echo "[OK] Started one-shot memolite-server (not managed by launchctl)"
  fi
}

cmd_stop() {
  if is_loaded; then
    launchctl kill SIGTERM "gui/$UID/$LABEL" || true
    echo "[OK] Stop signal sent: $LABEL"
  else
    pkill -f "memolite-server" >/dev/null 2>&1 || true
    echo "[INFO] launchctl service not loaded; tried pkill memolite-server"
  fi
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

cmd_status() {
  echo "=== memoLite Service Status ==="
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
