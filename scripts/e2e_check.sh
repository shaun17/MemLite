#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
ORG_ID="${ORG_ID:-demo-org}"
PROJECT_ID="${PROJECT_ID:-demo-project}"
SESSION_KEY="${SESSION_KEY:-demo-session}"
SESSION_ID="${SESSION_ID:-demo-session}"
USER_ID="${USER_ID:-demo-user}"

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
    {"uid":"ep-1","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","producer_id":"$USER_ID","producer_role":"user","sequence_num":1,"content":"My name is Wenren."},
    {"uid":"ep-2","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","producer_id":"$USER_ID","producer_role":"user","sequence_num":2,"content":"I love ramen."}
  ]
}
JSON
)
add_res="$(http_json POST /memories "$add_payload")"
json_has "$add_res" 'length >= 2' || fail "写入记忆失败: $add_res"
pass "episodic 写入成功"

log "5) 触发语义补偿（等待 1 秒）"
sleep 1

log "6) mixed 检索验证"
search_payload=$(cat <<JSON
{"query":"what food do i like","session_key":"$SESSION_KEY","session_id":"$SESSION_ID","semantic_set_id":"$SESSION_KEY","mode":"mixed"}
JSON
)
search_res="$(http_json POST /memories/search "$search_payload")"
json_has "$search_res" '.mode == "mixed" or .mode == "episodic" or .mode == "semantic"' || fail "search 返回异常: $search_res"
json_has "$search_res" '.episodic_matches | length >= 1' || fail "episodic 检索为空: $search_res"
pass "mixed 检索可用"

log "7) 配置生效验证：关闭 semantic"
http_json PATCH /memory-config/long-term '{"semantic_enabled":false}' >/dev/null
search_after_disable="$(http_json POST /memories/search "$search_payload")"
json_has "$search_after_disable" '.mode == "episodic"' || fail "关闭 semantic 后 mode 未降级为 episodic: $search_after_disable"
pass "memory-config 生效正常"

log "8) 删除验证"
del_payload=$(cat <<JSON
{"episode_uids":["ep-1","ep-2"],"semantic_set_id":"$SESSION_KEY"}
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

echo
pass "E2E 验证完成"
