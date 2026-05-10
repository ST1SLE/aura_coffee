#!/usr/bin/env bash
# Install deploy-user cron entries for backups and operations health checks.

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/production/install-ops-cron.sh [--tls] [--staging-auth] ENV_FILE [BACKUP_DIR] [LOG_DIR]

Installs a managed crontab block for the current Unix user:
  - daily Postgres backup, Monday-Saturday
  - weekly Postgres backup copy, Sunday
  - operations health check every 15 minutes

Tuning:
  AURA_BACKUP_DAILY_CRON    default: 17 2 * * 1-6
  AURA_BACKUP_WEEKLY_CRON   default: 17 2 * * 0
  AURA_OPS_HEALTH_CRON      default: */15 * * * *
USAGE
}

ROOT_DIR="${AURA_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE_FLAGS=()

while (($# > 0)); do
  case "$1" in
    --tls|--staging-auth)
      COMPOSE_FLAGS+=("$1")
      shift
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

if (($# < 1 || $# > 3)); then
  usage
  exit 2
fi

ENV_FILE="$1"
BACKUP_DIR="${2:-${AURA_BACKUP_DIR:-/var/backups/aura-coffee/postgres}}"
LOG_DIR="${3:-${AURA_OPS_LOG_DIR:-/opt/aura-coffee/ops-logs}}"
DAILY_CRON="${AURA_BACKUP_DAILY_CRON:-17 2 * * 1-6}"
WEEKLY_CRON="${AURA_BACKUP_WEEKLY_CRON:-17 2 * * 0}"
HEALTH_CRON="${AURA_OPS_HEALTH_CRON:-*/15 * * * *}"
MARKER_BEGIN="# BEGIN AURA_COFFEE_OPS"
MARKER_END="# END AURA_COFFEE_OPS"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "error: required command not found: $command_name" >&2
    exit 1
  fi
}

shell_quote() {
  local value="$1"
  printf "'%s'" "${value//\'/\'\\\'\'}"
}

validate_cron_schedule() {
  local name="$1"
  local schedule="$2"
  local fields

  read -r -a fields <<<"$schedule"
  if ((${#fields[@]} != 5)); then
    echo "error: $name must contain five cron fields, got '$schedule'" >&2
    exit 2
  fi
}

compose_flag_words() {
  local flag
  for flag in "${COMPOSE_FLAGS[@]}"; do
    printf ' %s' "$flag"
  done
}

require_command crontab
validate_cron_schedule "AURA_BACKUP_DAILY_CRON" "$DAILY_CRON"
validate_cron_schedule "AURA_BACKUP_WEEKLY_CRON" "$WEEKLY_CRON"
validate_cron_schedule "AURA_OPS_HEALTH_CRON" "$HEALTH_CRON"

mkdir -p -- "$BACKUP_DIR" "$LOG_DIR"
chmod 0700 "$BACKUP_DIR" "$LOG_DIR"

q_root="$(shell_quote "$ROOT_DIR")"
q_env="$(shell_quote "$ENV_FILE")"
q_backup="$(shell_quote "$BACKUP_DIR")"
q_log="$(shell_quote "$LOG_DIR")"
flags="$(compose_flag_words)"

daily_cmd="cd ${q_root} && scripts/production/backup-postgres.sh${flags} ${q_env} ${q_backup} >> ${q_log}/backup-postgres.log 2>&1"
weekly_cmd="cd ${q_root} && scripts/production/backup-postgres.sh${flags} --weekly ${q_env} ${q_backup} >> ${q_log}/backup-postgres.log 2>&1"
health_cmd="cd ${q_root} && scripts/production/check-ops-health.sh${flags} ${q_env} ${q_backup} >> ${q_log}/ops-health.log 2>&1"

current_cron="$(mktemp)"
next_cron="$(mktemp)"
trap 'rm -f "$current_cron" "$next_cron"' EXIT

crontab -l >"$current_cron" 2>/dev/null || true
awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" '
  $0 == begin {skip = 1; next}
  $0 == end {skip = 0; next}
  skip != 1 {print}
' "$current_cron" >"$next_cron"

{
  printf '%s\n' "$MARKER_BEGIN"
  printf 'SHELL=/bin/sh\n'
  printf 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n'
  printf '%s %s\n' "$DAILY_CRON" "$daily_cmd"
  printf '%s %s\n' "$WEEKLY_CRON" "$weekly_cmd"
  printf '%s %s\n' "$HEALTH_CRON" "$health_cmd"
  printf '%s\n' "$MARKER_END"
} >>"$next_cron"

crontab "$next_cron"

printf 'ops_cron_installed=yes\n'
printf 'backup_dir=%s\n' "$BACKUP_DIR"
printf 'log_dir=%s\n' "$LOG_DIR"
printf 'daily_schedule=%s\n' "$DAILY_CRON"
printf 'weekly_schedule=%s\n' "$WEEKLY_CRON"
printf 'health_schedule=%s\n' "$HEALTH_CRON"
