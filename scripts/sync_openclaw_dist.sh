#!/usr/bin/env bash
set -euo pipefail

# Sync openclaw plugin build artifacts into src/ so pip packages include them.
# Run after: cd integrations/openclaw && npm run build

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT_DIR/integrations/openclaw/dist"
DST="$ROOT_DIR/src/memolite/integrations/openclaw/dist"

if [[ ! -d "$SRC" ]]; then
  echo "[ERROR] Source dist not found: $SRC"
  echo "Run: cd integrations/openclaw && npm install && npm run build"
  exit 1
fi

mkdir -p "$DST"
cp "$SRC/index.mjs" "$DST/index.mjs"
cp "$SRC/index.d.ts" "$DST/index.d.ts" 2>/dev/null || true
cp "$SRC/index.mjs.map" "$DST/index.mjs.map" 2>/dev/null || true

echo "[OK] Synced openclaw dist -> $DST"
ls -la "$DST"
