#!/usr/bin/env bash
set -euo pipefail

# Sync openclaw plugin build artifacts + version into src/ so pip packages include them.
# Run after: cd integrations/openclaw && npm run build
# Also syncs pyproject.toml version into both package.json files

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT_DIR/integrations/openclaw/dist"
DST="$ROOT_DIR/src/memolite/integrations/openclaw/dist"
SRC_PKG="$ROOT_DIR/integrations/openclaw/package.json"
DST_PKG="$ROOT_DIR/src/memolite/integrations/openclaw/package.json"
PYPROJECT="$ROOT_DIR/pyproject.toml"

if [[ ! -d "$SRC" ]]; then
  echo "[ERROR] Source dist not found: $SRC"
  echo "Run: cd integrations/openclaw && npm install && npm run build"
  exit 1
fi

# 1. Sync dist files
mkdir -p "$DST"
cp "$SRC/index.mjs" "$DST/index.mjs"
cp "$SRC/index.d.ts" "$DST/index.d.ts" 2>/dev/null || true
cp "$SRC/index.mjs.map" "$DST/index.mjs.map" 2>/dev/null || true

# 2. Sync version from pyproject.toml into both package.json files
VERSION=$(grep -m1 '^version' "$PYPROJECT" | sed 's/.*"\(.*\)".*/\1/')
if [[ -n "$VERSION" ]]; then
  for pkg in "$SRC_PKG" "$DST_PKG"; do
    if [[ -f "$pkg" ]]; then
      python3 -c "
import json, pathlib
p = pathlib.Path('$pkg')
obj = json.loads(p.read_text())
obj['version'] = '$VERSION'
p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
"
    fi
  done
  echo "[OK] Synced version -> $VERSION"
fi

echo "[OK] Synced openclaw dist -> $DST"
ls -la "$DST"
