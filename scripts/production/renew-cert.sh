#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  cat >&2 <<'USAGE'
Usage: scripts/production/renew-cert.sh ENV_FILE [--staging-auth]

Examples:
  scripts/production/renew-cert.sh /opt/aura-coffee/.env.production
  scripts/production/renew-cert.sh /opt/aura-coffee/.env.production --staging-auth
USAGE
  exit 2
fi

ENV_FILE="$1"
shift

STAGING_AUTH_MODE=0
if [ "${1:-}" = "--staging-auth" ]; then
  STAGING_AUTH_MODE=1
elif [ "${1:-}" ]; then
  printf 'ERROR: unsupported option: %s\n' "$1" >&2
  exit 2
fi

[ -r "$ENV_FILE" ] || {
  printf 'ERROR: env file is not readable: %s\n' "$ENV_FILE" >&2
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

domain="$(value_of AURA_PUBLIC_DOMAIN)"
[ -n "$domain" ] || {
  printf 'ERROR: AURA_PUBLIC_DOMAIN is required\n' >&2
  exit 1
}

certbot_www="$(value_of AURA_CERTBOT_WWW_DIR)"
[ -n "$certbot_www" ] || certbot_www=/opt/aura-coffee/certbot-www

letsencrypt_dir="$(value_of AURA_LETSENCRYPT_DIR)"
[ -n "$letsencrypt_dir" ] || letsencrypt_dir=/etc/letsencrypt

mkdir -p "$certbot_www"

docker run --rm \
  -v "$letsencrypt_dir:/etc/letsencrypt" \
  -v /var/lib/letsencrypt:/var/lib/letsencrypt \
  -v "$certbot_www:/var/www/certbot" \
  certbot/certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --keep-until-expiring \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email \
  -d "$domain"

if [ "$STAGING_AUTH_MODE" -eq 1 ]; then
  scripts/production/compose.sh --tls --staging-auth "$ENV_FILE" exec -T nginx nginx -s reload
else
  scripts/production/compose.sh --tls "$ENV_FILE" exec -T nginx nginx -s reload
fi
