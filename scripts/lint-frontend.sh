#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Linting web/customer ==="
cd "$ROOT_DIR/web/customer" && npm run lint

echo ""
echo "=== Linting web/admin ==="
cd "$ROOT_DIR/web/admin" && npm run lint

echo ""
echo "All frontend linting passed."
