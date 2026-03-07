#!/usr/bin/env bash
set -euo pipefail

KUZU_PATH="${KUZU_PATH:-$HOME/.memlite/kuzu}"
PYTHON_BIN="${PYTHON_BIN:-$(pwd)/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] Python not found: $PYTHON_BIN"
  echo "Hint: 在仓库根目录执行 source .venv/bin/activate 或设置 PYTHON_BIN"
  exit 1
fi

if [[ ! -e "$KUZU_PATH" ]]; then
  echo "[ERROR] Kùzu path not found: $KUZU_PATH"
  exit 1
fi

cat <<'MSG'
[INFO] 如果出现文件锁错误（Could not set lock），请先停掉 memlite-server 再执行本脚本。
MSG

"$PYTHON_BIN" - <<'PY'
import os
import sys
from pathlib import Path

try:
    import kuzu
except Exception as e:
    print(f"[ERROR] import kuzu failed: {e}")
    sys.exit(1)

kuzu_path = Path(os.environ.get("KUZU_PATH", str(Path.home()/".memlite"/"kuzu")))

try:
    db = kuzu.Database(str(kuzu_path))
    conn = kuzu.Connection(db)
except Exception as e:
    print(f"[ERROR] open kuzu failed: {e}")
    sys.exit(2)

def q(sql: str):
    res = conn.execute(sql)
    if res.has_next():
        return res.get_next()[0]
    return None

queries = [
    ("Episode 节点数", "MATCH (n:Episode) RETURN count(n)"),
    ("Derivative 节点数", "MATCH (n:Derivative) RETURN count(n)"),
    ("DERIVED_FROM 边数", "MATCH ()-[r:DERIVED_FROM]->() RETURN count(r)"),
]

print("=== Kùzu 概览 ===")
for name, sql in queries:
    try:
        print(f"{name}: {q(sql)}")
    except Exception as e:
        print(f"{name}: ERROR - {e}")

print("\n=== Episode 样本(前10) ===")
try:
    res = conn.execute("MATCH (n:Episode) RETURN n.uid, n.session_id, n.content ORDER BY n.uid LIMIT 10")
    while res.has_next():
        row = res.get_next()
        print(f"uid={row[0]} | session_id={row[1]} | content={row[2]}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n=== Derivative 样本(前10) ===")
try:
    res = conn.execute("MATCH (n:Derivative) RETURN n.uid, n.episode_uid, n.content ORDER BY n.uid LIMIT 10")
    while res.has_next():
        row = res.get_next()
        print(f"uid={row[0]} | episode_uid={row[1]} | content={row[2]}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n=== DERIVED_FROM 关系样本(前20) ===")
try:
    res = conn.execute(
        "MATCH (d:Derivative)-[r:DERIVED_FROM]->(e:Episode) "
        "RETURN d.uid, e.uid, r.relation_type ORDER BY d.uid LIMIT 20"
    )
    while res.has_next():
        row = res.get_next()
        print(f"derivative={row[0]} -> episode={row[1]} | relation_type={row[2]}")
except Exception as e:
    print(f"ERROR: {e}")
PY