#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/production/get-staging-otp.sh PHONE

Print the current closed-staging SMS OTP for PHONE, waiting briefly until the
sms-worker marks it sent.

Environment overrides:
  AURA_STAGING_SSH_TARGET   default: deploy@212.8.226.214
  AURA_STAGING_SSH_KEY      default: ~/.ssh/aura-vps
  AURA_OTP_WAIT_SECONDS     default: 12
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

PHONE="${1:-}"
if [ -z "$PHONE" ]; then
  usage
  exit 2
fi

SSH_TARGET="${AURA_STAGING_SSH_TARGET:-deploy@212.8.226.214}"
SSH_KEY="${AURA_STAGING_SSH_KEY:-$HOME/.ssh/aura-vps}"
WAIT_SECONDS="${AURA_OTP_WAIT_SECONDS:-12}"

case "$WAIT_SECONDS" in
  ''|*[!0-9]*)
    printf 'AURA_OTP_WAIT_SECONDS must be an integer number of seconds\n' >&2
    exit 2
    ;;
esac

read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail

cd /opt/aura-coffee/app
COMPOSE=(scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production)

phone_hash=$("${COMPOSE[@]}" exec -T -e PHONE="$PHONE" core-api python - <<'PY' 2>/dev/null
import os
from core_api.utils.crypto import hash_phone
from core_api.utils.phone import normalize_phone

print(hash_phone(normalize_phone(os.environ["PHONE"])))
PY
)

deadline=$((SECONDS + WAIT_SECONDS))
while [ "$SECONDS" -le "$deadline" ]; do
  raw=$("${COMPOSE[@]}" exec -T redis redis-cli --raw GET "otp:$phone_hash" 2>/dev/null || true)
  code=$(RAW="$raw" python3 - <<'PY'
import json
import os

try:
    data = json.loads(os.environ.get("RAW") or "")
except Exception:
    raise SystemExit(0)

if data.get("status") == "sent" and data.get("code"):
    print(data["code"])
PY
)
  if [ -n "$code" ]; then
    printf '%s\n' "$code"
    exit 0
  fi
  sleep 0.5
done

printf 'No sent OTP found before timeout. Click Get Code, wait a second, then retry.\n' >&2
exit 2
REMOTE

if command -v timeout >/dev/null 2>&1; then
  SSH_PREFIX=(timeout "$((WAIT_SECONDS + 25))s")
else
  SSH_PREFIX=()
fi

"${SSH_PREFIX[@]}" ssh \
  -i "$SSH_KEY" \
  -o IdentitiesOnly=yes \
  -o BatchMode=yes \
  -o ConnectTimeout=8 \
  "$SSH_TARGET" \
  "PHONE=$(printf '%q' "$PHONE") WAIT_SECONDS=$(printf '%q' "$WAIT_SECONDS") bash -lc $(printf '%q' "$REMOTE_SCRIPT")"
