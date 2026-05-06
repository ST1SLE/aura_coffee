#!/usr/bin/env sh
set -eu

TLS_MODE=0
STAGING_AUTH_MODE=0
while [ "${1:-}" = "--tls" ] || [ "${1:-}" = "--staging-auth" ]; do
  case "$1" in
    --tls)
      TLS_MODE=1
      ;;
    --staging-auth)
      TLS_MODE=1
      STAGING_AUTH_MODE=1
      ;;
  esac
  shift
done

if [ "$#" -lt 2 ]; then
  cat >&2 <<'USAGE'
Usage: scripts/production/compose.sh [--tls] [--staging-auth] ENV_FILE [docker compose args...]

Examples:
  scripts/production/compose.sh .env.production.example config
  scripts/production/compose.sh --tls .env.production.example config
  scripts/production/compose.sh --tls --staging-auth .env.production.example config
  scripts/production/compose.sh /opt/aura-coffee/.env.production up -d --build
USAGE
  exit 2
fi

ENV_FILE="$1"
shift

[ -r "$ENV_FILE" ] || {
  printf 'ERROR: env file is not readable: %s\n' "$ENV_FILE" >&2
  exit 1
}

if [ "$STAGING_AUTH_MODE" -eq 1 ]; then
  set -- docker compose \
    --env-file "$ENV_FILE" \
    -f docker-compose.yml \
    -f docker-compose.production.yml \
    -f docker-compose.production.tls.yml \
    -f docker-compose.production.staging-auth.yml \
    "$@"
elif [ "$TLS_MODE" -eq 1 ]; then
  set -- docker compose \
    --env-file "$ENV_FILE" \
    -f docker-compose.yml \
    -f docker-compose.production.yml \
    -f docker-compose.production.tls.yml \
    "$@"
else
  set -- docker compose \
    --env-file "$ENV_FILE" \
    -f docker-compose.yml \
    -f docker-compose.production.yml \
    "$@"
fi

exec env \
  -u AURA_ENV \
  -u AURA_MENU_MEDIA_DIR \
  -u AURA_PUBLIC_DOMAIN \
  -u AURA_CERTBOT_WWW_DIR \
  -u AURA_LETSENCRYPT_DIR \
  -u AURA_BASIC_AUTH_REALM \
  -u AURA_BASIC_AUTH_USER_FILE \
  -u AURA_STAGING_ACCESS_COOKIE \
  -u AURA_STAGING_HTPASSWD_FILE \
  -u POSTGRES_USER \
  -u POSTGRES_PASSWORD \
  -u POSTGRES_DB \
  -u DATABASE_URL \
  -u TEST_DATABASE_URL \
  -u REDIS_URL \
  -u CORS_ORIGINS \
  -u JWT_SECRET_KEY \
  -u ENCRYPTION_KEY \
  -u SMS_BACKEND \
  -u SMSRU_API_KEY \
  -u YANDEX_MAPS_SUGGEST_API_KEY \
  -u YANDEX_MAPS_GEOCODER_API_KEY \
  -u YANDEX_MAPS_API_KEY \
  -u YUKASSA_BACKEND \
  -u YUKASSA_SHOP_ID \
  -u YUKASSA_SECRET_KEY \
  -u YUKASSA_BASE_URL \
  -u YUKASSA_WEBHOOK_IPS \
  -u YUKASSA_WEBHOOK_SIGNATURE_SECRET \
  -u YUKASSA_WEBHOOK_SIGNATURE_HEADER \
  -u YUKASSA_FAKE_OUTCOME \
  -u POSTGRES_PORT \
  -u REDIS_PORT \
  -u CORE_API_PORT \
  -u WEB_CUSTOMER_PORT \
  -u WEB_ADMIN_PORT \
  -u NGINX_PORT \
  -u NGINX_HTTP_PORT \
  -u NGINX_HTTPS_PORT \
  -u PAYMENT_WEBHOOK_PORT \
  -u ADMIN_LOGIN \
  -u ADMIN_PASSWORD \
  AURA_ENV_FILE="$ENV_FILE" \
  "$@"
