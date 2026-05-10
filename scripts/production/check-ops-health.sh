#!/usr/bin/env bash
# Non-destructive production operations checks for backups, TLS, and services.
# shellcheck disable=SC2016

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/production/check-ops-health.sh [--tls] [--staging-auth] [--domain DOMAIN] ENV_FILE [BACKUP_DIR]

Checks:
  - required Compose services are running
  - public /health is OK when AURA_PUBLIC_DOMAIN or --domain is set
  - TLS certificate is not close to expiry when a domain is available
  - latest daily backup is fresh
  - disk usage is below threshold
  - provider modes/key presence are reported without printing secrets

Tuning:
  AURA_OPS_BACKUP_MAX_AGE_HOURS  default: 30
  AURA_OPS_DISK_MAX_PERCENT      default: 85
  AURA_OPS_TLS_MIN_DAYS          default: 21
USAGE
}

ROOT_DIR="${AURA_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE_FLAGS=()
DOMAIN=""

while (($# > 0)); do
  case "$1" in
    --tls|--staging-auth)
      COMPOSE_FLAGS+=("$1")
      shift
      ;;
    --domain)
      if (($# < 2)); then
        echo "error: --domain requires a value" >&2
        exit 2
      fi
      DOMAIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "error: unknown option: $1" >&2
      usage
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if (($# < 1 || $# > 2)); then
  usage
  exit 2
fi

ENV_FILE="$1"
BACKUP_DIR="${2:-${AURA_BACKUP_DIR:-/var/backups/aura-coffee/postgres}}"
BACKUP_MAX_AGE_HOURS="${AURA_OPS_BACKUP_MAX_AGE_HOURS:-30}"
DISK_MAX_PERCENT="${AURA_OPS_DISK_MAX_PERCENT:-85}"
TLS_MIN_DAYS="${AURA_OPS_TLS_MIN_DAYS:-21}"

fail_count=0
warn_count=0

require_positive_int() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "error: $name must be a positive integer, got '$value'" >&2
    exit 2
  fi
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "error: required command not found: $command_name" >&2
    exit 1
  fi
}

ok() {
  printf 'ok: %s\n' "$1"
}

warn() {
  warn_count=$((warn_count + 1))
  printf 'warn: %s\n' "$1"
}

fail() {
  fail_count=$((fail_count + 1))
  printf 'fail: %s\n' "$1"
}

run_compose() {
  (
    cd "$ROOT_DIR"
    scripts/production/compose.sh "${COMPOSE_FLAGS[@]}" "$ENV_FILE" "$@"
  )
}

env_get() {
  local key="$1"
  local fallback="${2:-}"
  local value=""

  if [[ -r "$ENV_FILE" ]]; then
    value="$(awk -F= -v key="$key" '
      $0 !~ /^[[:space:]]*#/ && $1 == key {
        sub(/^[^=]*=/, "")
        print
      }
    ' "$ENV_FILE" | tail -n1)"
  fi

  if [[ -z "$value" ]]; then
    printf '%s' "$fallback"
    return
  fi

  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

check_services() {
  local expected=(
    postgres
    redis
    core-api
    core-api-worker
    payment-worker
    payment-webhook
    sms-worker
    scheduler
    nginx
  )
  local running
  local service

  running="$(run_compose ps --services --status running 2>/dev/null || true)"
  for service in "${expected[@]}"; do
    if grep -Fx "$service" <<<"$running" >/dev/null; then
      ok "service_running=$service"
    else
      fail "service_not_running=$service"
    fi
  done
}

check_public_health() {
  local domain="$1"
  local body
  local curl_args=(-fsS --max-time 10)
  local staging_cookie

  if [[ -z "$domain" ]]; then
    warn "public_health_skipped=no_domain"
    return
  fi

  staging_cookie="$(env_get AURA_STAGING_ACCESS_COOKIE "")"
  if [[ -n "$staging_cookie" ]]; then
    curl_args+=(-H "Cookie: aura_staging=${staging_cookie}")
  fi

  if body="$(curl "${curl_args[@]}" "https://${domain}/health" 2>/dev/null)" \
    && [[ "$(tr -d '[:space:]' <<<"$body")" == *'"status":"ok"'* ]]; then
    ok "public_health=https://${domain}/health"
  else
    fail "public_health_failed=https://${domain}/health"
  fi
}

check_tls() {
  local domain="$1"
  local min_seconds
  local end_date

  if [[ -z "$domain" ]]; then
    warn "tls_skipped=no_domain"
    return
  fi

  min_seconds=$((TLS_MIN_DAYS * 24 * 60 * 60))
  if end_date="$(
    openssl s_client -servername "$domain" -connect "${domain}:443" </dev/null 2>/dev/null \
      | openssl x509 -noout -enddate 2>/dev/null \
      | cut -d= -f2-
  )"; then
    if openssl s_client -servername "$domain" -connect "${domain}:443" </dev/null 2>/dev/null \
      | openssl x509 -noout -checkend "$min_seconds" >/dev/null 2>&1; then
      ok "tls_valid_until=${end_date}"
    else
      fail "tls_expires_within_days=${TLS_MIN_DAYS} end_date=${end_date}"
    fi
  else
    fail "tls_check_failed=${domain}"
  fi
}

check_backups() {
  local latest_file
  local latest_mtime
  local now
  local age_hours
  local daily_count
  local weekly_count

  if [[ ! -d "$BACKUP_DIR" ]]; then
    fail "backup_dir_missing=${BACKUP_DIR}"
    return
  fi

  daily_count="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'aura_daily_*.sql.gz' | wc -l)"
  weekly_count="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'aura_weekly_*.sql.gz' | wc -l)"
  if ((daily_count == 0)); then
    fail "backup_daily_count=0"
    return
  fi

  latest_file="$(
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'aura_daily_*.sql.gz' -printf '%T@ %p\n' \
      | sort -nr \
      | head -n1 \
      | cut -d' ' -f2-
  )"
  latest_mtime="$(stat -c '%Y' "$latest_file")"
  now="$(date +%s)"
  age_hours=$(((now - latest_mtime) / 3600))

  if ((age_hours <= BACKUP_MAX_AGE_HOURS)); then
    ok "latest_daily_backup=$(basename "$latest_file") age_hours=${age_hours}"
  else
    fail "latest_daily_backup_stale=$(basename "$latest_file") age_hours=${age_hours}"
  fi

  if ((weekly_count > 0)); then
    ok "weekly_backup_count=${weekly_count}"
  else
    warn "weekly_backup_count=0"
  fi
}

check_disk_path() {
  local path="$1"
  local label="$2"
  local use_percent

  if [[ ! -e "$path" ]]; then
    fail "disk_path_missing=${label}"
    return
  fi

  use_percent="$(df -P "$path" 2>/dev/null | awk 'NR == 2 {gsub("%", "", $5); print $5}')"
  if [[ -z "$use_percent" ]]; then
    fail "disk_check_failed=${label}"
    return
  fi

  if ((use_percent < DISK_MAX_PERCENT)); then
    ok "disk_${label}_used_percent=${use_percent}"
  else
    fail "disk_${label}_used_percent=${use_percent}"
  fi
}

check_provider_modes() {
  local sms_backend
  local yukassa_backend
  local yandex_suggest
  local yandex_geocoder

  sms_backend="$(env_get SMS_BACKEND "unset")"
  yukassa_backend="$(env_get YUKASSA_BACKEND "unset")"
  yandex_suggest="$(env_get YANDEX_MAPS_SUGGEST_API_KEY "")"
  yandex_geocoder="$(env_get YANDEX_MAPS_GEOCODER_API_KEY "")"

  ok "provider_sms_backend=${sms_backend}"
  ok "provider_yukassa_backend=${yukassa_backend}"
  if [[ -n "$yandex_suggest" && -n "$yandex_geocoder" ]]; then
    ok "provider_yandex_split_keys_present=yes"
  else
    warn "provider_yandex_split_keys_present=no"
  fi
  warn "provider_dashboard_alerts_manual=sms_balance_yandex_quota_yukassa_failures"
}

check_cron_marker() {
  if command -v crontab >/dev/null 2>&1 && crontab -l 2>/dev/null \
    | grep -F "BEGIN AURA_COFFEE_OPS" >/dev/null; then
    ok "ops_cron_marker=present"
  else
    warn "ops_cron_marker=missing"
  fi
}

require_positive_int "AURA_OPS_BACKUP_MAX_AGE_HOURS" "$BACKUP_MAX_AGE_HOURS"
require_positive_int "AURA_OPS_DISK_MAX_PERCENT" "$DISK_MAX_PERCENT"
require_positive_int "AURA_OPS_TLS_MIN_DAYS" "$TLS_MIN_DAYS"
require_command docker
require_command curl
require_command openssl

if [[ -z "$DOMAIN" ]]; then
  DOMAIN="${AURA_OPS_DOMAIN:-$(env_get AURA_PUBLIC_DOMAIN "")}"
fi

printf 'ops_check_started_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
check_services
check_public_health "$DOMAIN"
check_tls "$DOMAIN"
check_backups
check_disk_path "/" "root"
check_disk_path "$BACKUP_DIR" "backup"
check_provider_modes
check_cron_marker
printf 'ops_check_finished_utc=%s failures=%s warnings=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$fail_count" "$warn_count"

if ((fail_count > 0)); then
  exit 1
fi
