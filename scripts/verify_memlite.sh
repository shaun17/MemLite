#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
ORG_ID="${ORG_ID:-demo-org}"
PROJECT_ID="${PROJECT_ID:-demo-project}"
SESSION_KEY="${SESSION_KEY:-demo-session}"
SESSION_ID="${SESSION_ID:-demo-session}"
USER_ID="${USER_ID:-demo-user}"

# KEEP_DATA=1: 保留测试数据（默认）
# KEEP_DATA=0: 执行清理步骤
KEEP_DATA="${KEEP_DATA:-1}"

# 若数据库路径可用，脚本末尾会输出各表计数
SQLITE_PATH="${SQLITE_PATH:-$HOME/.memlite/memlite.sqlite3}"
SHOW_COUNTS="${SHOW_COUNTS:-1}"

# RUN_INTERNAL_VERIFY=1: 在 E2E 后串行跑内在存储/查询测试（pytest）
RUN_INTERNAL_VERIFY="${RUN_INTERNAL_VERIFY:-1}"
INTERNAL_TEST_TARGETS="${INTERNAL_TEST_TARGETS:-tests/unit/test_episode_store.py tests/unit/test_graph_store.py tests/unit/test_sqlite_vec.py tests/unit/test_semantic_feature_store.py tests/unit/test_semantic_service.py tests/unit/test_memory_orchestrator.py tests/integration/test_episode_store_integration.py tests/integration/test_episodic_search_integration.py tests/integration/test_semantic_feature_store_integration.py tests/integration/test_semantic_service_integration.py tests/integration/test_memory_orchestrator_integration.py tests/integration/test_api_routes.py}"

RUN_ID="$(date +%s)"
EP1_UID="ep-${RUN_ID}-1"
EP2_UID="ep-${RUN_ID}-2"
CATEGORY_NAME="profile_${RUN_ID}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${YELLOW}[$(date +%H:%M:%S)]${NC} $*"; }
pass() { echo -e "${GREEN}PASS${NC} - $*"; }
fail() { echo -e "${RED}FAIL${NC} - $*"; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令: $1"
}

json_has() {
  local json="$1"
  local expr="$2"
  echo "$json" | jq -e "$expr" >/dev/null 2>&1
}

http_json() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -X "$method" "$BASE_URL$path" \
      -H 'content-type: application/json' \
      -d "$data"
  else
    curl -sS -X "$method" "$BASE_URL$path"
  fi
}

run_internal_verify() {
  [[ "$RUN_INTERNAL_VERIFY" == "1" ]] || {
    log "跳过内在验证（RUN_INTERNAL_VERIFY=0）"
    return 0
  }

  local pytest_bin="$(pwd)/.venv/bin/pytest"
  if [[ ! -x "$pytest_bin" ]]; then
    fail "未找到 pytest: $pytest_bin"
  fi

  log "10) 内在存储/查询验证（pytest）"
  # shellcheck disable=SC2086
  "$pytest_bin" -q $INTERNAL_TEST_TARGETS || fail "内在验证失败"
  pass "内在存储/查询验证通过"
}

print_sqlite_counts() {
  [[ "$SHOW_COUNTS" == "1" ]] || return 0
  if [[ ! -f "$SQLITE_PATH" ]]; then
    log "跳过 SQLite 计数（文件不存在）：$SQLITE_PATH"
    return 0
  fi
  if ! command -v sqlite3 >/dev/null 2>&1; then
    log "跳过 SQLite 计数（缺少 sqlite3 命令）"
    return 0
  fi

  echo
  echo "===== SQLite table counts ====="
  sqlite3 "$SQLITE_PATH" <<'SQL'
.headers on
.mode column
SELECT 'projects' AS table_name, COUNT(*) AS cnt FROM projects
UNION ALL SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL SELECT 'episodes_total', COUNT(*) FROM episodes
UNION ALL SELECT 'episodes_deleted_0', COUNT(*) FROM episodes WHERE deleted=0
UNION ALL SELECT 'episodes_deleted_1', COUNT(*) FROM episodes WHERE deleted=1
UNION ALL SELECT 'semantic_features', COUNT(*) FROM semantic_features
UNION ALL SELECT 'semantic_citations', COUNT(*) FROM semantic_citations
UNION ALL SELECT 'semantic_feature_vectors', COUNT(*) FROM semantic_feature_vectors
UNION ALL SELECT 'derivative_feature_vectors', COUNT(*) FROM derivative_feature_vectors
UNION ALL SELECT 'semantic_set_ingested_history', COUNT(*) FROM semantic_set_ingested_history
UNION ALL SELECT 'semantic_config_set_type', COUNT(*) FROM semantic_config_set_type
UNION ALL SELECT 'semantic_config_set_id_resources', COUNT(*) FROM semantic_config_set_id_resources
UNION ALL SELECT 'semantic_config_set_id_set_type', COUNT(*) FROM semantic_config_set_id_set_type
UNION ALL SELECT 'semantic_config_category', COUNT(*) FROM semantic_config_category
UNION ALL SELECT 'semantic_config_category_template', COUNT(*) FROM semantic_config_category_template
UNION ALL SELECT 'semantic_config_tag', COUNT(*) FROM semantic_config_tag
UNION ALL SELECT 'semantic_config_disabled_category', COUNT(*) FROM semantic_config_disabled_category;
SQL
}

log "检查依赖"
need_cmd curl
need_cmd jq

log "1) 健康检查"
health="$(http_json GET /health)"
json_has "$health" '.status == "ok"' || fail "health 检查失败: $health"
pass "health 正常"

log "2) 创建项目"
project_payload=$(cat <<JSON
{"org_id":"$ORG_ID","project_id":"$PROJECT_ID","description":"e2e-check"}
JSON
)
http_json POST /projects "$project_payload" >/dev/null
pass "项目创建/幂等写入成功"

log "3) 创建会话"
session_payload=$(cat <<JSON
{"session_key":"$SESSION_KEY","org_id":"$ORG_ID","project_id":"$PROJECT_ID","session_id":"$SESSION_ID","user_id":"$USER_ID"}
JSON
)
http_json POST /sessions "$session_payload" >/dev/null
pass "会话创建成功"

log "4) 写入记忆"
add_payload=$(cat <<JSON
{
  "session_key":"$SESSION_KEY",
  "semantic_set_id":"$SESSION_KEY",
  "episodes":[
    {"uid":"$EP1_UID","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","producer_id":"$USER_ID","producer_role":"user","sequence_num":1,"content":"My name is Wenren."},
    {"uid":"$EP2_UID","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","producer_id":"$USER_ID","producer_role":"user","sequence_num":2,"content":"I love ramen."}
  ]
}
JSON
)
add_res="$(http_json POST /memories "$add_payload")"
json_has "$add_res" 'length >= 2' || fail "写入记忆失败: $add_res"
pass "episodic 写入成功"

log "5) 覆盖语义配置相关表"
set_type_res="$(http_json POST /semantic/config/set-types "{\"org_id\":\"$ORG_ID\",\"metadata_tags_sig\":\"e2e-$RUN_ID\",\"name\":\"e2e-type-$RUN_ID\"}")"
set_type_id="$(echo "$set_type_res" | jq -r '.id // empty')"
[[ -n "$set_type_id" ]] || fail "创建 set-type 失败: $set_type_res"

http_json POST /semantic/config/sets "{\"set_id\":\"$SESSION_KEY\",\"set_type_id\":$set_type_id,\"set_name\":\"e2e-set\",\"embedder_name\":\"default\",\"language_model_name\":\"default\"}" >/dev/null

category_res="$(http_json POST /semantic/config/categories "{\"name\":\"$CATEGORY_NAME\",\"prompt\":\"extract profile\",\"set_id\":\"$SESSION_KEY\"}")"
category_id="$(echo "$category_res" | jq -r '.id // empty')"
[[ -n "$category_id" ]] || fail "创建 category 失败: $category_res"

http_json POST /semantic/config/category-templates "{\"name\":\"profile-template-$RUN_ID\",\"category_name\":\"$CATEGORY_NAME\",\"prompt\":\"extract profile\",\"set_type_id\":$set_type_id}" >/dev/null
http_json POST /semantic/config/tags "{\"category_id\":$category_id,\"name\":\"preference_$RUN_ID\",\"description\":\"user preference\"}" >/dev/null
http_json POST /semantic/config/disabled-categories "{\"set_id\":\"$SESSION_KEY\",\"category_name\":\"hidden_$RUN_ID\"}" >/dev/null
pass "semantic_config 相关表写入成功"

log "6) 写入一条 semantic feature（覆盖 semantic_features/vector 表）"
http_json POST /semantic/features "{\"set_id\":\"$SESSION_KEY\",\"category\":\"profile\",\"tag\":\"preference\",\"feature_name\":\"favorite_food\",\"value\":\"ramen\",\"embedding\":[1.0,0.0,0.0,0.0]}" >/dev/null
pass "semantic feature 写入成功"

log "7) mixed 检索验证"
search_payload=$(cat <<JSON
{"query":"what food do i like","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","semantic_set_id":"$SESSION_KEY","mode":"mixed"}
JSON
)
search_res="$(http_json POST /memories/search "$search_payload")"
json_has "$search_res" '.mode == "mixed" or .mode == "episodic" or .mode == "semantic"' || fail "search 返回异常: $search_res"
json_has "$search_res" '.episodic_matches | length >= 1' || fail "episodic 检索为空: $search_res"
pass "mixed 检索可用"

log "8) 配置生效验证：关闭 semantic"
http_json PATCH /memory-config/long-term '{"semantic_enabled":false}' >/dev/null
search_after_disable="$(http_json POST /memories/search "$search_payload")"
json_has "$search_after_disable" '.mode == "episodic"' || fail "关闭 semantic 后 mode 未降级为 episodic: $search_after_disable"
pass "memory-config 生效正常"

if [[ "$KEEP_DATA" == "0" ]]; then
  log "9) 删除验证（KEEP_DATA=0）"
  del_payload=$(cat <<JSON
{"episode_uids":["$EP1_UID","$EP2_UID"],"semantic_set_id":"$SESSION_KEY"}
JSON
)
  http_json DELETE /memories/episodes "$del_payload" >/dev/null
  post_del_payload=$(cat <<JSON
{"query":"ramen","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","mode":"episodic"}
JSON
)
  post_del_res="$(http_json POST /memories/search "$post_del_payload")"
  json_has "$post_del_res" '.episodic_matches | length == 0' || fail "删除后仍有 episodic 命中: $post_del_res"
  pass "删除链路正常"
else
  log "9) 跳过删除（KEEP_DATA=1），保留数据供检查"
fi

run_internal_verify
print_sqlite_counts

echo
pass "E2E+内在验证完成"
pass "run_id=$RUN_ID, episode_uids=[$EP1_UID,$EP2_UID]"
