#!/usr/bin/env bash
# Browser smoke verification for the running Aura Coffee Compose stack.
#
# The Playwright suite resets rows owned by known Phase 4 QA seed identifiers
# and QA users via scripts/reset-qa-data.sh. It does not drop databases, remove
# Docker volumes, stop services, or touch non-QA user data.

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

require_env_file() {
  if [[ ! -f .env ]]; then
    cat >&2 <<EOF
error: .env not found.

Run:
  ./scripts/setup-worktree-env.sh
  ./scripts/up.sh

Then rerun this verifier.
EOF
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
    cat >&2 <<EOF
error: Docker Compose service '$service' is not running.

This verifier does not start or stop the stack. Bring it up first:
  ./scripts/up.sh
EOF
    exit 1
  fi
}

require_command docker
require_command npm
require_env_file

required_services=(
  postgres
  redis
  core-api
  core-api-worker
  payment-worker
  payment-webhook
  sms-worker
  web-customer
  web-admin
  nginx
)

for service in "${required_services[@]}"; do
  require_running_service "$service"
done

echo ""
echo "=== npm --prefix tests/e2e ci ==="
npm --prefix tests/e2e ci

if [[ "${AURA_E2E_SKIP_BROWSER_INSTALL:-0}" != "1" ]]; then
  if [[ "${CI:-}" == "true" ]]; then
    echo ""
    echo "=== npm --prefix tests/e2e exec -- playwright install --with-deps chromium ==="
    npm --prefix tests/e2e exec -- playwright install --with-deps chromium
  else
    echo ""
    echo "=== npm --prefix tests/e2e exec -- playwright install chromium ==="
    npm --prefix tests/e2e exec -- playwright install chromium
  fi
fi

NGINX_PORT="$(env_get NGINX_PORT 8240)"
export AURA_E2E_BASE_URL="${AURA_E2E_BASE_URL:-http://127.0.0.1:${NGINX_PORT}}"

echo ""
echo "=== npm --prefix tests/e2e run test ==="
npm --prefix tests/e2e run test
