#!/usr/bin/env sh
set -eu

if [ "$#" -lt 2 ]; then
  cat >&2 <<'USAGE'
Usage: scripts/production/compose.sh ENV_FILE [docker compose args...]

Examples:
  scripts/production/compose.sh .env.production.example config
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

exec env \
  -u AURA_ENV \
  -u AURA_MENU_MEDIA_DIR \
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
  -u PAYMENT_WEBHOOK_PORT \
  -u ADMIN_LOGIN \
  -u ADMIN_PASSWORD \
  AURA_ENV_FILE="$ENV_FILE" \
  docker compose \
    --env-file "$ENV_FILE" \
    -f docker-compose.yml \
    -f docker-compose.production.yml \
    "$@"
