#!/usr/bin/env bash
# Bootstrap a per-worktree .env with a collision-free host port offset.
#
# - Derives a deterministic starting offset from sha1(worktree path).
# - Probes POSTGRES/REDIS/CORE_API/WEB_CUSTOMER/WEB_ADMIN/NGINX and
#   PAYMENT_WEBHOOK ports against 127.0.0.1 via bash /dev/tcp; if any is bound,
#   bumps offset by +10 and retries up to MAX_ATTEMPTS times.
# - On success, writes .env from .env.example with every port replaced and
#   CORS_ORIGINS patched to match the new WEB_CUSTOMER_PORT / WEB_ADMIN_PORT.
# - Idempotent: re-run to pick a fresh offset if your current .env starts
#   colliding with another stack that came up later.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

EXAMPLE=".env.example"
TARGET=".env"
MAX_ATTEMPTS=20

if [[ ! -f "$EXAMPLE" ]]; then
    echo "error: $EXAMPLE not found at $REPO_ROOT" >&2
    exit 1
fi

# Production guard: refuse to run on a host marked as production unless the
# caller explicitly sets FORCE=1. Triggers are any of:
#   - .env.production exists in the repo root
#   - AURA_PRODUCTION_HOST=1 in the environment
#   - /etc/aura-coffee/production marker file exists
if [[ "${FORCE:-0}" != "1" ]]; then
    reason=""
    if [[ -f "$REPO_ROOT/.env.production" ]]; then
        reason=".env.production exists at repo root"
    elif [[ "${AURA_PRODUCTION_HOST:-0}" == "1" ]]; then
        reason="AURA_PRODUCTION_HOST=1 is set"
    elif [[ -f "/etc/aura-coffee/production" ]]; then
        reason="/etc/aura-coffee/production marker exists"
    fi
    if [[ -n "$reason" ]]; then
        echo "error: refusing to run — $reason" >&2
        echo "       this script is a dev-worktree bootstrap and would overwrite" >&2
        echo "       .env with .env.example dev defaults. re-run with FORCE=1 to" >&2
        echo "       override (you almost certainly do not want to)." >&2
        exit 1
    fi
fi

# Base defaults (must mirror .env.example / docker-compose.yml fallbacks)
BASE_POSTGRES=5433
BASE_REDIS=6379
BASE_CORE_API=8000
BASE_WEB_CUSTOMER=5173
BASE_WEB_ADMIN=5174
BASE_NGINX=80
BASE_PAYMENT_WEBHOOK=8241

# Deterministic starting offset from sha1(worktree path), in steps of 10.
seed_hex="$(printf '%s' "$REPO_ROOT" | sha1sum | cut -c1-8)"
seed_int=$((16#$seed_hex))
start_offset=$(( (seed_int % 20) * 10 ))

port_is_free() {
    local port="$1"
    # Open a TCP connection to 127.0.0.1:$port; success means something is
    # listening, so the port is NOT free.
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        exec 3<&- 3>&-
        return 1
    fi
    return 0
}

set_is_free() {
    local offset="$1"
    local ports=(
        $((BASE_POSTGRES + offset))
        $((BASE_REDIS + offset))
        $((BASE_CORE_API + offset))
        $((BASE_WEB_CUSTOMER + offset))
        $((BASE_WEB_ADMIN + offset))
        $((BASE_NGINX + offset))
        $((BASE_PAYMENT_WEBHOOK + offset))
    )
    for p in "${ports[@]}"; do
        if ! port_is_free "$p"; then
            echo "  port $p busy" >&2
            return 1
        fi
    done
    return 0
}

echo "Seed offset for $REPO_ROOT: +$start_offset"

chosen_offset=""
for (( i=0; i<MAX_ATTEMPTS; i++ )); do
    offset=$(( (start_offset + i * 10) % 200 ))
    echo "Trying offset +$offset ..." >&2
    if set_is_free "$offset"; then
        chosen_offset="$offset"
        break
    fi
done

if [[ -z "$chosen_offset" ]]; then
    echo "error: could not find a free port set after $MAX_ATTEMPTS attempts" >&2
    exit 1
fi

POSTGRES_PORT=$((BASE_POSTGRES + chosen_offset))
REDIS_PORT=$((BASE_REDIS + chosen_offset))
CORE_API_PORT=$((BASE_CORE_API + chosen_offset))
WEB_CUSTOMER_PORT=$((BASE_WEB_CUSTOMER + chosen_offset))
WEB_ADMIN_PORT=$((BASE_WEB_ADMIN + chosen_offset))
NGINX_PORT=$((BASE_NGINX + chosen_offset))
PAYMENT_WEBHOOK_PORT=$((BASE_PAYMENT_WEBHOOK + chosen_offset))

echo "Chosen offset: +$chosen_offset"
echo "  POSTGRES_PORT=$POSTGRES_PORT"
echo "  REDIS_PORT=$REDIS_PORT"
echo "  CORE_API_PORT=$CORE_API_PORT"
echo "  WEB_CUSTOMER_PORT=$WEB_CUSTOMER_PORT"
echo "  WEB_ADMIN_PORT=$WEB_ADMIN_PORT"
echo "  NGINX_PORT=$NGINX_PORT"
echo "  PAYMENT_WEBHOOK_PORT=$PAYMENT_WEBHOOK_PORT"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Start from .env.example, then overwrite the port lines and CORS_ORIGINS.
cp "$EXAMPLE" "$tmp"

sed -i \
    -e "s|^POSTGRES_PORT=.*|POSTGRES_PORT=$POSTGRES_PORT|" \
    -e "s|^REDIS_PORT=.*|REDIS_PORT=$REDIS_PORT|" \
    -e "s|^CORE_API_PORT=.*|CORE_API_PORT=$CORE_API_PORT|" \
    -e "s|^WEB_CUSTOMER_PORT=.*|WEB_CUSTOMER_PORT=$WEB_CUSTOMER_PORT|" \
    -e "s|^WEB_ADMIN_PORT=.*|WEB_ADMIN_PORT=$WEB_ADMIN_PORT|" \
    -e "s|^NGINX_PORT=.*|NGINX_PORT=$NGINX_PORT|" \
    -e "s|^PAYMENT_WEBHOOK_PORT=.*|PAYMENT_WEBHOOK_PORT=$PAYMENT_WEBHOOK_PORT|" \
    -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=http://localhost:$WEB_CUSTOMER_PORT,http://localhost:$WEB_ADMIN_PORT|" \
    "$tmp"

mv "$tmp" "$TARGET"
trap - EXIT

echo "Wrote $TARGET with offset +$chosen_offset"
