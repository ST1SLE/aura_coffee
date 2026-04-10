#!/usr/bin/env bash
# Bring the full dev stack up and print the REAL host-side URLs.
#
# Why this exists: the Vite dev servers inside web-customer / web-admin
# containers log lines like "Local: http://localhost:5173/" — those ports
# are container-internal. When WEB_CUSTOMER_PORT / WEB_ADMIN_PORT are bumped
# per worktree, following the Vite banner produces "connection refused" on
# the host. This wrapper reads .env after `docker compose up -d` and prints
# the actual host URLs so nobody has to guess.
#
# Usage:
#   ./scripts/up.sh                 # bring everything up
#   ./scripts/up.sh --build         # forwarded to `docker compose up -d`
#   ./scripts/up.sh --build core-api
#
# Extra args are forwarded verbatim to `docker compose up -d`.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

ENV_FILE=".env"

if [[ ! -f "$ENV_FILE" ]]; then
  cat >&2 <<EOF
error: $ENV_FILE not found in repo root.

Run the worktree bootstrap first:
  ./scripts/setup-worktree-env.sh

It will generate a .env with a collision-free set of host ports.
EOF
  exit 1
fi

# Parse a single key from .env WITHOUT sourcing it. Sourcing would execute
# arbitrary shell from .env content (e.g. values with $, backticks, or
# semicolons). cut -d= -f2- preserves everything after the first '='.
env_get() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2-
}

# Run compose. Forward any extra args so `./scripts/up.sh --build core-api`
# does the obvious thing.
docker compose up -d "$@"

# Best-effort health wait. Poll `docker compose ps` for up to ~30s. If
# services are still starting after the timeout, we still print the banner
# but with a heads-up so the dev knows why curl might briefly fail.
wait_for_healthy() {
  local deadline=$(( SECONDS + 30 ))
  while (( SECONDS < deadline )); do
    # If any non-one-shot service is not running/healthy, keep waiting.
    local bad
    bad="$(docker compose ps --format json 2>/dev/null \
      | grep -E '"State":"(created|restarting|exited|dead)"' || true)"
    if [[ -z "$bad" ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

HEALTH_NOTE=""
if ! wait_for_healthy; then
  HEALTH_NOTE=" (services may still be starting — retry in a moment if a URL fails)"
fi

WEB_CUSTOMER_PORT="$(env_get WEB_CUSTOMER_PORT)"
WEB_ADMIN_PORT="$(env_get WEB_ADMIN_PORT)"
CORE_API_PORT="$(env_get CORE_API_PORT)"
NGINX_PORT="$(env_get NGINX_PORT)"

cat <<EOF

╔══════════════════════════════════════════════════════════════════╗
║  Aura Coffee — dev stack is up${HEALTH_NOTE}
╠══════════════════════════════════════════════════════════════════╣
║  Canonical entry point (via nginx):
║    → http://localhost:${NGINX_PORT}/
║
║  Direct access (debugging):
║    Customer SPA  → http://localhost:${WEB_CUSTOMER_PORT}/
║    Admin SPA     → http://localhost:${WEB_ADMIN_PORT}/
║    Core API      → http://localhost:${CORE_API_PORT}/
╠══════════════════════════════════════════════════════════════════╣
║  ⚠  IGNORE the "Local: http://localhost:5173/" and
║     "Local: http://localhost:5174/" lines printed by the
║     web-customer / web-admin containers. Those are
║     container-internal ports and will NOT work on the host
║     when you have bumped host ports per worktree.
╚══════════════════════════════════════════════════════════════════╝

EOF
