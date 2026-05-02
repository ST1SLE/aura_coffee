#!/usr/bin/env bash
# Python dependency vulnerability gate for Aura Coffee.
#
# Runs from the host through uvx so the audit does not depend on pip-audit being
# baked into each runtime image. The host Python path defaults to the known-good
# interpreter documented in AGENTS.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

cd "$ROOT_DIR"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "error: required command not found: $command_name" >&2
    exit 1
  fi
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "error: Python interpreter is not executable: $PYTHON_BIN" >&2
  exit 1
fi

require_command uvx

projects=(
  services/core-api
  services/payment-worker
  services/sms-worker
  packages/shared
)

for project in "${projects[@]}"; do
  echo ""
  echo "=== uvx --python $PYTHON_BIN pip-audit --progress-spinner off $project ==="
  uvx --python "$PYTHON_BIN" pip-audit --progress-spinner off "$project"
done
