#!/usr/bin/env bash
# Restore a PostgreSQL dump into an isolated scratch database and verify it.
# shellcheck disable=SC2016

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/production/restore-postgres.sh [--tls] [--staging-auth] [--keep-db] ENV_FILE BACKUP_FILE [SCRATCH_DB]

Restores BACKUP_FILE into a scratch database, runs Alembic upgrade head against
that scratch database, prints non-sensitive row-count evidence, and drops the
scratch database unless --keep-db is supplied.
USAGE
}

ROOT_DIR="${AURA_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE_FLAGS=()
DROP_AFTER=1

while (($# > 0)); do
  case "$1" in
    --tls|--staging-auth)
      COMPOSE_FLAGS+=("$1")
      shift
      ;;
    --keep-db)
      DROP_AFTER=0
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

if (($# < 2 || $# > 3)); then
  usage
  exit 2
fi

ENV_FILE="$1"
BACKUP_FILE="$2"
SCRATCH_DB="${3:-aura_restore_$(date -u +%Y%m%dT%H%M%SZ)}"
CREATED_DB=0

run_compose() {
  (
    cd "$ROOT_DIR"
    scripts/production/compose.sh "${COMPOSE_FLAGS[@]}" "$ENV_FILE" "$@"
  )
}

if [[ ! -r "$BACKUP_FILE" ]]; then
  echo "error: backup file is not readable: $BACKUP_FILE" >&2
  exit 1
fi

if [[ ! "$SCRATCH_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "error: scratch database name is not safe: $SCRATCH_DB" >&2
  exit 2
fi

cleanup() {
  if ((DROP_AFTER == 1 && CREATED_DB == 1)); then
    run_compose exec -T postgres sh -lc 'dropdb -U "$POSTGRES_USER" --if-exists "$1"' sh "$SCRATCH_DB" >/dev/null
    printf 'scratch_db_dropped=%s\n' "$SCRATCH_DB"
  fi
}
trap cleanup EXIT

current_db="$(run_compose exec -T postgres sh -lc 'printf "%s" "$POSTGRES_DB"' | tr -d '\r')"
if [[ "$SCRATCH_DB" == "$current_db" ]]; then
  echo "error: refusing to restore over POSTGRES_DB ($current_db)" >&2
  exit 2
fi

run_compose exec -T postgres sh -lc 'createdb -U "$POSTGRES_USER" "$1"' sh "$SCRATCH_DB"
CREATED_DB=1
printf 'scratch_db_created=%s\n' "$SCRATCH_DB"

gzip -dc "$BACKUP_FILE" \
  | run_compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" >/dev/null' sh "$SCRATCH_DB"
printf 'restore_sql=ok\n'

run_compose exec -T core-api sh -lc '
set -eu
scratch_db="$1"
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${scratch_db}"
cd /app/database
alembic upgrade head >/tmp/aura_restore_alembic.log
alembic current
' sh "$SCRATCH_DB"
printf 'alembic_upgrade=ok\n'

run_compose exec -T postgres sh -lc '
set -eu
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -At <<SQL
SELECT '"'"'table_count='"'"' || count(*)
FROM information_schema.tables
WHERE table_schema = '"'"'public'"'"' AND table_type = '"'"'BASE TABLE'"'"';
SELECT '"'"'menu_items='"'"' || count(*) FROM menu_items;
SELECT '"'"'users='"'"' || count(*) FROM users;
SELECT '"'"'alembic_version='"'"' || version_num FROM alembic_version LIMIT 1;
SQL
' sh "$SCRATCH_DB"

if ((DROP_AFTER == 0)); then
  printf 'scratch_db_kept=%s\n' "$SCRATCH_DB"
fi
