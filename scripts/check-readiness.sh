#!/usr/bin/env bash
# Non-destructive readiness checks for the running Aura Coffee compose stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "error: required command not found: $command_name" >&2
    exit 1
  fi
}

env_get() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(grep -E "^${key}=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  if [[ -n "$value" ]]; then
    printf "%s" "$value"
  else
    printf "%s" "$fallback"
  fi
}

require_running_service() {
  local service="$1"
  if ! docker compose ps --services --status running 2>/dev/null | grep -Fx "$service" >/dev/null; then
    echo "error: Docker Compose service '$service' is not running." >&2
    exit 1
  fi
}

check_http_health() {
  local label="$1"
  local url="$2"
  local body
  local compact

  echo "=== readiness: $label $url ==="
  body="$(curl -fsS --max-time 5 "$url")"
  compact="$(printf "%s" "$body" | tr -d '[:space:]')"
  if [[ "$compact" != *'"status":"ok"'* ]]; then
    echo "error: $label health response did not include status=ok: $body" >&2
    exit 1
  fi
}

check_celery_workers() {
  local output
  local pong_count

  echo "=== readiness: celery worker ping ==="
  output="$(docker compose exec -T payment-worker celery -A payment_worker.main inspect ping --timeout=5)"
  printf "%s\n" "$output"
  pong_count="$(printf "%s\n" "$output" | grep -c "pong" || true)"
  if (( pong_count < 3 )); then
    echo "error: expected at least 3 Celery worker pongs, got $pong_count" >&2
    exit 1
  fi
}

require_command curl
require_command docker

if [[ ! -f .env ]]; then
  echo "error: .env not found. Run ./scripts/setup-worktree-env.sh and ./scripts/up.sh first." >&2
  exit 1
fi

for service in core-api payment-webhook nginx core-api-worker payment-worker sms-worker; do
  require_running_service "$service"
done

CORE_API_PORT="$(env_get CORE_API_PORT 8000)"
PAYMENT_WEBHOOK_PORT="$(env_get PAYMENT_WEBHOOK_PORT 8241)"
NGINX_PORT="$(env_get NGINX_PORT 8240)"

check_http_health "core-api direct" "http://127.0.0.1:${CORE_API_PORT}/health"
check_http_health "payment-webhook direct" "http://127.0.0.1:${PAYMENT_WEBHOOK_PORT}/health"
check_http_health "nginx canonical" "http://127.0.0.1:${NGINX_PORT}/health"
check_celery_workers

echo ""
echo "Readiness checks passed."
