#!/usr/bin/env bash
# Full local verification gate for Aura Coffee.
#
# This script is intentionally non-destructive: it requires an already-running
# Docker Compose stack and never stops services, deletes volumes, or resets data.
# Backend checks run inside containers to avoid host Python SSL drift.

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

require_running_service() {
  local service="$1"
  if ! docker compose ps --services --status running 2>/dev/null | grep -Fx "$service" >/dev/null; then
    cat >&2 <<EOF
error: Docker Compose service '$service' is not running.

This verifier does not start or mutate the stack. Bring it up first:
  ./scripts/up.sh
EOF
    exit 1
  fi
}

run_compose() {
  local service="$1"
  shift
  echo ""
  echo "=== docker compose exec -T $service $* ==="
  docker compose exec -T "$service" "$@"
}

run_optional_python_audit() {
  echo ""
  echo "=== optional Python dependency audit ==="
  if docker compose exec -T core-api sh -lc 'command -v pip-audit >/dev/null 2>&1'; then
    docker compose exec -T core-api pip-audit
  else
    echo "skip: pip-audit is not installed in the core-api image."
    echo "      Install it in the verification image before making this gate mandatory."
  fi
}

require_command docker
require_env_file

required_services=(
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

./scripts/check-readiness.sh

run_compose core-api sh -lc 'cd /app/database && alembic check'
run_compose core-api sh -lc 'cd /app/database && alembic upgrade head'

run_compose core-api ruff check services/core-api/src database packages/shared/src
run_compose payment-worker ruff check services/payment-worker/src
run_compose sms-worker ruff check services/sms-worker/src

run_compose core-api pytest packages/shared/tests/ -v
run_compose core-api pytest services/core-api/tests/ -v
run_compose payment-worker pytest services/payment-worker/tests/ -v
run_compose sms-worker pytest services/sms-worker/tests/ -v

run_compose web-customer npm run lint
run_compose web-customer npm run typecheck
run_compose web-customer npm run test
run_compose web-customer npm audit --audit-level=high

run_compose web-admin npm run lint
run_compose web-admin npm run typecheck
run_compose web-admin npm run test
run_compose web-admin npm audit --audit-level=high

run_optional_python_audit

echo ""
echo "Full verification passed."
