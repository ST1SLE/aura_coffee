#!/usr/bin/env sh
set -eu

ENV_FILE="${1:-.env.production}"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

value_of() {
  key="$1"
  awk -F= -v key="$key" '
    $0 !~ /^[[:space:]]*#/ && $1 == key {
      sub(/^[^=]*=/, "")
      value = $0
    }
    END {
      if (value != "") print value
    }
  ' "$ENV_FILE"
}

require_present() {
  key="$1"
  value="$(value_of "$key")"
  [ -n "$value" ] || fail "$key is required"
}

require_not_placeholder() {
  key="$1"
  value="$(value_of "$key")"
  [ -n "$value" ] || fail "$key is required"
  case "$value" in
    REPLACE_*|change-me*|dev-secret|admin123|aura_secret)
      fail "$key still has a placeholder/dev value"
      ;;
  esac
}

[ -r "$ENV_FILE" ] || fail "env file is not readable: $ENV_FILE"

require_present AURA_ENV
[ "$(value_of AURA_ENV)" = "production" ] || fail "AURA_ENV must be production"

for key in \
  POSTGRES_USER \
  POSTGRES_DB \
  DATABASE_URL \
  REDIS_URL \
  CORS_ORIGINS \
  JWT_SECRET_KEY \
  ENCRYPTION_KEY \
  SMS_BACKEND \
  YUKASSA_BACKEND \
  YUKASSA_BASE_URL \
  YUKASSA_WEBHOOK_IPS \
  ADMIN_LOGIN \
  ADMIN_PASSWORD
do
  require_present "$key"
done

for key in POSTGRES_PASSWORD JWT_SECRET_KEY ENCRYPTION_KEY ADMIN_PASSWORD
do
  require_not_placeholder "$key"
done

case "$(value_of CORS_ORIGINS)" in
  *localhost*|*127.0.0.1*)
    fail "CORS_ORIGINS must not contain localhost in production"
    ;;
esac

encryption_key="$(value_of ENCRYPTION_KEY)"
printf '%s' "$encryption_key" | grep -Eq '^[0-9a-fA-F]{64}$' \
  || fail "ENCRYPTION_KEY must be 64 hex characters"

sms_backend="$(value_of SMS_BACKEND)"
case "$sms_backend" in
  log|smsru) ;;
  *) fail "SMS_BACKEND must be log or smsru" ;;
esac
if [ "$sms_backend" = "smsru" ]; then
  require_not_placeholder SMSRU_API_KEY
fi

yukassa_backend="$(value_of YUKASSA_BACKEND)"
case "$yukassa_backend" in
  fake|live) ;;
  *) fail "YUKASSA_BACKEND must be fake or live" ;;
esac
if [ "$yukassa_backend" = "live" ]; then
  require_not_placeholder YUKASSA_SHOP_ID
  require_not_placeholder YUKASSA_SECRET_KEY
  case "$(value_of YUKASSA_BASE_URL)" in
    *sandbox*|*test*|*localhost*|*127.0.0.1*)
      fail "YUKASSA_BASE_URL is not allowed for live mode"
      ;;
  esac
fi

printf 'OK: %s is production-shaped and contains no known placeholders.\n' "$ENV_FILE"
