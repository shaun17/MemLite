#!/usr/bin/env bash
set -euo pipefail

# memoLite service manager
# - macOS: LaunchAgent
# - Linux: systemd --user
# Default runtime: 127.0.0.1:18731

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_MEMOLITE_BIN="$(command -v memolite-server || true)"
if [[ -z "$DEFAULT_MEMOLITE_BIN" && -x "$HOME/.local/bin/memolite-server" ]]; then
  DEFAULT_MEMOLITE_BIN="$HOME/.local/bin/memolite-server"
fi
if [[ -z "$DEFAULT_MEMOLITE_BIN" && -x "$ROOT_DIR/.venv/bin/memolite-server" ]]; then
  DEFAULT_MEMOLITE_BIN="$ROOT_DIR/.venv/bin/memolite-server"
fi

MEMLITE_BIN="${MEMLITE_BIN:-$DEFAULT_MEMOLITE_BIN}"
HOST="${MEMLITE_HOST:-127.0.0.1}"
PORT="${MEMLITE_PORT:-18731}"
SQLITE_PATH="${MEMLITE_SQLITE_PATH:-$HOME/.memolite/memolite.sqlite3}"
KUZU_PATH="${MEMLITE_KUZU_PATH:-$HOME/.memolite/kuzu}"

LABEL="ai.memolite.server"
OS="$(uname -s)"
IS_MACOS=0
IS_LINUX=0
if [[ "$OS" == "Darwin" ]]; then
  IS_MACOS=1
elif [[ "$OS" == "Linux" ]]; then
  IS_LINUX=1
fi

PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="/tmp/memolite"
OUT_LOG="$LOG_DIR/memolite.out.log"
ERR_LOG="$LOG_DIR/memolite.err.log"

SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SYSTEMD_UNIT_PATH="$SYSTEMD_USER_DIR/$LABEL.service"

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
- install: create service definition; does NOT auto-enable unless --enable
- enable: enable auto-start
- disable: disable auto-start
- start/restart: runtime control only; do NOT change auto-start policy
EOF
}

ensure_dirs() {
  mkdir -p "$LOG_DIR"
  mkdir -p "$(dirname "$SQLITE_PATH")"
}

ensure_bins() {
  [[ -n "$MEMLITE_BIN" && -x "$MEMLITE_BIN" ]] || {
    echo "[ERROR] memolite-server not found."
    echo "Checked: ${MEMLITE_BIN:-<empty>}"
    echo "Hint: ensure memolite is installed (pipx install memolite), or set MEMLITE_BIN explicitly."
    exit 1
  }
}

# ---------- macOS (LaunchAgent) ----------

macos_is_loaded() {
  launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1
}

macos_write_plist() {
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

macos_install() {
  local enable="${1:-0}"
  macos_write_plist
  echo "[OK] Installed plist: $PLIST_PATH"
  if [[ "$enable" == "1" ]]; then
    macos_enable
  else
    echo "[INFO] Auto-start not enabled. Run: $0 enable"
  fi
}

macos_uninstall() {
  macos_disable || true
  if [[ -f "$PLIST_PATH" ]]; then
    rm -f "$PLIST_PATH"
    echo "[OK] Removed $PLIST_PATH"
  else
    echo "[INFO] plist not found: $PLIST_PATH"
  fi
}

macos_enable() {
  [[ -f "$PLIST_PATH" ]] || macos_write_plist
  if macos_is_loaded; then
    echo "[INFO] Service already loaded"
  else
    launchctl bootstrap "gui/$UID" "$PLIST_PATH"
    echo "[OK] Enabled (loaded): $LABEL"
  fi
  macos_start
}

macos_disable() {
  if macos_is_loaded; then
    launchctl bootout "gui/$UID/$LABEL"
    echo "[OK] Disabled (unloaded): $LABEL"
  else
    echo "[INFO] Service not loaded"
  fi
}

macos_start() {
  if macos_is_loaded; then
    launchctl kickstart -k "gui/$UID/$LABEL"
    echo "[OK] Started: $LABEL"
  else
    echo "[WARN] Service not enabled. Running one-shot in background instead."
    MEMLITE_HOST="$HOST" MEMLITE_PORT="$PORT" MEMLITE_SQLITE_PATH="$SQLITE_PATH" MEMLITE_KUZU_PATH="$KUZU_PATH" \
      nohup "$MEMLITE_BIN" >/tmp/memolite-oneshot.out 2>/tmp/memolite-oneshot.err &
    echo "[OK] Started one-shot memolite-server (not managed by launchctl)"
  fi
}

macos_stop() {
  if macos_is_loaded; then
    launchctl kill SIGTERM "gui/$UID/$LABEL" || true
    echo "[OK] Stop signal sent: $LABEL"
  else
    pkill -f "memolite-server" >/dev/null 2>&1 || true
    echo "[INFO] launchctl service not loaded; tried pkill memolite-server"
  fi
}

macos_restart() {
  macos_stop
  sleep 1
  macos_start
}

macos_status() {
  echo "=== memoLite Service Status (macOS) ==="
  echo "Label: $LABEL"
  echo "Plist: $PLIST_PATH"
  echo "Endpoint: http://$HOST:$PORT"
  echo "SQLite: $SQLITE_PATH"
  echo "Kùzu: $KUZU_PATH"
  echo "---"
  if macos_is_loaded; then
    echo "launchctl: loaded"
    launchctl print "gui/$UID/$LABEL" | sed -n '1,80p'
  else
    echo "launchctl: not loaded"
  fi
  echo "---"
  curl -sS "http://$HOST:$PORT/health" && echo || echo "health: unavailable"
}

# ---------- Linux (systemd --user) ----------

linux_need_systemctl() {
  command -v systemctl >/dev/null 2>&1 || {
    echo "[ERROR] systemctl not found"
    exit 1
  }
}

linux_write_unit() {
  ensure_dirs
  ensure_bins
  linux_need_systemctl
  mkdir -p "$SYSTEMD_USER_DIR"
  cat >"$SYSTEMD_UNIT_PATH" <<EOF
[Unit]
Description=memoLite server
After=network.target

[Service]
Type=simple
ExecStart=$MEMLITE_BIN
Restart=always
RestartSec=2
Environment=MEMLITE_HOST=$HOST
Environment=MEMLITE_PORT=$PORT
Environment=MEMLITE_SQLITE_PATH=$SQLITE_PATH
Environment=MEMLITE_KUZU_PATH=$KUZU_PATH
StandardOutput=append:$OUT_LOG
StandardError=append:$ERR_LOG

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
}

linux_install() {
  local enable="${1:-0}"
  linux_write_unit
  echo "[OK] Installed unit: $SYSTEMD_UNIT_PATH"
  if [[ "$enable" == "1" ]]; then
    linux_enable
  else
    echo "[INFO] Auto-start not enabled. Run: $0 enable"
  fi
}

linux_uninstall() {
  linux_disable || true
  if [[ -f "$SYSTEMD_UNIT_PATH" ]]; then
    rm -f "$SYSTEMD_UNIT_PATH"
    systemctl --user daemon-reload || true
    echo "[OK] Removed $SYSTEMD_UNIT_PATH"
  else
    echo "[INFO] unit not found: $SYSTEMD_UNIT_PATH"
  fi
}

linux_enable() {
  [[ -f "$SYSTEMD_UNIT_PATH" ]] || linux_write_unit
  systemctl --user enable "$LABEL.service"
  echo "[OK] Enabled: $LABEL"
  linux_start
}

linux_disable() {
  if systemctl --user list-unit-files "$LABEL.service" >/dev/null 2>&1; then
    systemctl --user disable "$LABEL.service" >/dev/null 2>&1 || true
    systemctl --user stop "$LABEL.service" >/dev/null 2>&1 || true
    echo "[OK] Disabled: $LABEL"
  else
    echo "[INFO] unit not registered"
  fi
}

linux_start() {
  if systemctl --user list-unit-files "$LABEL.service" >/dev/null 2>&1; then
    systemctl --user start "$LABEL.service"
    echo "[OK] Started: $LABEL"
  else
    echo "[WARN] Service not installed. Running one-shot in background instead."
    MEMLITE_HOST="$HOST" MEMLITE_PORT="$PORT" MEMLITE_SQLITE_PATH="$SQLITE_PATH" MEMLITE_KUZU_PATH="$KUZU_PATH" \
      nohup "$MEMLITE_BIN" >/tmp/memolite-oneshot.out 2>/tmp/memolite-oneshot.err &
    echo "[OK] Started one-shot memolite-server (not managed by systemd)"
  fi
}

linux_stop() {
  if systemctl --user list-unit-files "$LABEL.service" >/dev/null 2>&1; then
    systemctl --user stop "$LABEL.service" || true
    echo "[OK] Stopped: $LABEL"
  else
    pkill -f "memolite-server" >/dev/null 2>&1 || true
    echo "[INFO] systemd unit not found; tried pkill memolite-server"
  fi
}

linux_restart() {
  linux_stop
  sleep 1
  linux_start
}

linux_status() {
  echo "=== memoLite Service Status (Linux systemd) ==="
  echo "Label: $LABEL"
  echo "Unit: $SYSTEMD_UNIT_PATH"
  echo "Endpoint: http://$HOST:$PORT"
  echo "SQLite: $SQLITE_PATH"
  echo "Kùzu: $KUZU_PATH"
  echo "---"
  if systemctl --user list-unit-files "$LABEL.service" >/dev/null 2>&1; then
    systemctl --user status "$LABEL.service" --no-pager || true
    echo "enabled: $(systemctl --user is-enabled "$LABEL.service" 2>/dev/null || echo no)"
  else
    echo "systemd: unit not installed"
  fi
  echo "---"
  curl -sS "http://$HOST:$PORT/health" && echo || echo "health: unavailable"
}

# ---------- Dispatcher ----------

cmd_install() {
  local enable="0"
  if [[ "${1:-}" == "--enable" ]]; then
    enable="1"
  fi
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_install "$enable"
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_install "$enable"
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_uninstall() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_uninstall
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_uninstall
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_enable() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_enable
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_enable
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_disable() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_disable
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_disable
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_start() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_start
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_start
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_stop() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_stop
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_stop
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_restart() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_restart
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_restart
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

cmd_status() {
  if [[ "$IS_MACOS" == "1" ]]; then
    macos_status
  elif [[ "$IS_LINUX" == "1" ]]; then
    linux_status
  else
    echo "[ERROR] Unsupported OS: $OS"
    exit 1
  fi
}

main() {
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
