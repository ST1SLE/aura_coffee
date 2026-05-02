#!/usr/bin/env bash
# Non-volume QA data reset for a running local Aura Coffee Compose stack.
#
# This does not run `docker compose down -v`, drop volumes, or reset arbitrary
# user data. The Python seed module enforces the dev/test/local environment
# guard and only removes deterministic Phase 4 QA fixture rows before reseeding.

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

Then rerun this reset.
EOF
    exit 1
  fi
}

require_running_service() {
  local service="$1"
  if ! docker compose ps --services --status running 2>/dev/null | grep -Fx "$service" >/dev/null; then
    cat >&2 <<EOF
error: Docker Compose service '$service' is not running.

This reset does not start or mutate the stack lifecycle. Bring it up first:
  ./scripts/up.sh
EOF
    exit 1
  fi
}

require_command docker
require_env_file
require_running_service core-api
require_running_service postgres

echo "=== reset deterministic QA data and re-run manual seed ==="
docker compose exec -T core-api python -m database.seeds.reset_qa_data
