#!/usr/bin/env bash
# Create a timestamped PostgreSQL dump from the production Compose stack.
# shellcheck disable=SC2016

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/production/backup-postgres.sh [--tls] [--staging-auth] [--weekly] ENV_FILE [BACKUP_DIR]

Creates:
  BACKUP_DIR/aura_daily_YYYYMMDDTHHMMSSZ.sql.gz

With --weekly, also creates:
  BACKUP_DIR/aura_weekly_YYYYMMDDTHHMMSSZ.sql.gz

Retention is controlled by:
  AURA_BACKUP_KEEP_DAILY   default: 7
  AURA_BACKUP_KEEP_WEEKLY  default: 4
USAGE
}

ROOT_DIR="${AURA_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE_FLAGS=()
MAKE_WEEKLY=0

while (($# > 0)); do
  case "$1" in
    --tls|--staging-auth)
      COMPOSE_FLAGS+=("$1")
      shift
      ;;
    --weekly)
      MAKE_WEEKLY=1
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

if (($# < 1 || $# > 2)); then
  usage
  exit 2
fi

ENV_FILE="$1"
BACKUP_DIR="${2:-${AURA_BACKUP_DIR:-/var/backups/aura-coffee/postgres}}"
KEEP_DAILY="${AURA_BACKUP_KEEP_DAILY:-7}"
KEEP_WEEKLY="${AURA_BACKUP_KEEP_WEEKLY:-4}"

require_positive_int() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "error: $name must be a positive integer, got '$value'" >&2
    exit 2
  fi
}

run_compose() {
  (
    cd "$ROOT_DIR"
    scripts/production/compose.sh "${COMPOSE_FLAGS[@]}" "$ENV_FILE" "$@"
  )
}

prune_backups() {
  local prefix="$1"
  local keep="$2"
  local files=()

  mapfile -t files < <(
    find "$BACKUP_DIR" -maxdepth 1 -type f -name "${prefix}*.sql.gz" -printf '%f\n' \
      | sort -r
  )

  if ((${#files[@]} <= keep)); then
    return
  fi

  local stale=("${files[@]:keep}")
  local name
  for name in "${stale[@]}"; do
    rm -f -- "$BACKUP_DIR/$name"
    printf 'pruned=%s\n' "$BACKUP_DIR/$name"
  done
}

require_positive_int "AURA_BACKUP_KEEP_DAILY" "$KEEP_DAILY"
require_positive_int "AURA_BACKUP_KEEP_WEEKLY" "$KEEP_WEEKLY"

mkdir -p -- "$BACKUP_DIR"
chmod 0700 "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
daily_file="$BACKUP_DIR/aura_daily_${timestamp}.sql.gz"
tmp_file="${daily_file}.tmp.$$"
weekly_file=""

cleanup() {
  rm -f -- "$tmp_file"
}
trap cleanup EXIT

run_compose exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -c > "$tmp_file"

gzip -t "$tmp_file"
chmod 0600 "$tmp_file"
mv -- "$tmp_file" "$daily_file"

if ((MAKE_WEEKLY == 1)); then
  weekly_file="$BACKUP_DIR/aura_weekly_${timestamp}.sql.gz"
  cp -p -- "$daily_file" "$weekly_file"
fi

prune_backups "aura_daily_" "$KEEP_DAILY"
prune_backups "aura_weekly_" "$KEEP_WEEKLY"

printf 'backup_file=%s\n' "$daily_file"
printf 'backup_size_bytes=%s\n' "$(wc -c < "$daily_file")"
if [[ -n "$weekly_file" ]]; then
  printf 'weekly_backup_file=%s\n' "$weekly_file"
  printf 'weekly_backup_size_bytes=%s\n' "$(wc -c < "$weekly_file")"
fi
