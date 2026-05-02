#!/usr/bin/env bash
# Fast local verification gate for Aura Coffee.
#
# This script is intentionally non-destructive: it does not start, stop, reset,
# or delete Compose services, databases, or volumes. Backend checks run inside
# the existing Docker stack to avoid host Python SSL drift.

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

run_step() {
  echo ""
  echo "=== $* ==="
  "$@"
}

run_compose() {
  local service="$1"
  shift
  echo ""
  echo "=== docker compose exec -T $service $* ==="
  docker compose exec -T "$service" "$@"
}

require_command docker
require_command npm
require_env_file

require_running_service core-api
require_running_service payment-worker
require_running_service sms-worker

run_compose core-api ruff check services/core-api/src database packages/shared/src
run_compose payment-worker ruff check services/payment-worker/src
run_compose sms-worker ruff check services/sms-worker/src

run_step npm --prefix web/customer run lint
run_step npm --prefix web/customer run typecheck
run_step npm --prefix web/admin run lint
run_step npm --prefix web/admin run typecheck

run_compose core-api pytest \
  services/core-api/tests/test_route_coverage.py \
  services/core-api/tests/test_rbac_matrix.py \
  -q

run_compose sms-worker pytest \
  services/sms-worker/tests/test_otp_task_log_backend.py::test_send_otp_sms_emits_ldd_marker_and_redacts_logs \
  -q

echo ""
echo "Fast verification passed."
