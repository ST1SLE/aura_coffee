#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Formatting web/customer ==="
cd "$ROOT_DIR/web/customer" && npm run format

echo ""
echo "=== Formatting web/admin ==="
cd "$ROOT_DIR/web/admin" && npm run format

echo ""
echo "All frontend formatting complete."
