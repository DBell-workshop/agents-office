#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "[1/5] health"
curl -s "$BASE_URL/api/v1/health" >/dev/null

echo "[2/5] create course"
COURSE_JSON=$(curl -s -X POST "$BASE_URL/api/v1/training/courses" \
  -H 'Content-Type: application/json' \
  -d '{"product_id":"prod-001","product_name":"Phone X","objective":"demo","required_points":["battery"],"product_facts":{"installments":"12 installments"}}')
COURSE_ID=$(echo "$COURSE_JSON" | sed -n 's/.*"course_id":"\([^"]*\)".*/\1/p')

echo "[3/5] generate content"
GEN_JSON=$(curl -s -X POST "$BASE_URL/api/v1/training/courses/$COURSE_ID:generate-content" \
  -H 'Content-Type: application/json' \
  -d '{"scene":"in_store"}')
GEN_TASK_ID=$(echo "$GEN_JSON" | sed -n 's/.*"task_id":"\([^"]*\)".*/\1/p')
curl -s "$BASE_URL/api/v1/tasks/$GEN_TASK_ID" >/dev/null

echo "[4/5] create comparison"
CMP_JSON=$(curl -s -X POST "$BASE_URL/api/v1/comparison/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"source_product_id":"prod-001","source_product_name":"Phone X","targets":[{"platform":"jd","url":"https://item.jd.com/mock"},{"platform":"taobao","url":"https://detail.tmall.com/mock"}]}')
CMP_ID=$(echo "$CMP_JSON" | sed -n 's/.*"comparison_task_id":"\([^"]*\)".*/\1/p')

echo "[5/5] run comparison"
RUN_JSON=$(curl -s -X POST "$BASE_URL/api/v1/comparison/tasks/$CMP_ID:run" \
  -H 'Content-Type: application/json' \
  -d '{"template_version":"v1"}')
RUN_TASK_ID=$(echo "$RUN_JSON" | sed -n 's/.*"task_id":"\([^"]*\)".*/\1/p')

RESULT=$(curl -s "$BASE_URL/api/v1/tasks/$RUN_TASK_ID")
echo "$RESULT" | rg -q '"status":"succeeded"'

echo "Smoke test passed"
