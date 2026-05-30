#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8081}"

curl -fsS "$BASE_URL/" >/dev/null
curl -fsS "$BASE_URL/api/auth/health" >/dev/null || true
curl -fsS "$BASE_URL/api/catalog/health" >/dev/null || true
curl -fsS "$BASE_URL/api/generation/health" >/dev/null || true
curl -fsS "$BASE_URL/api/workflow/health" >/dev/null || true

echo "Generated HTTP access logs for nginx and backend services"
