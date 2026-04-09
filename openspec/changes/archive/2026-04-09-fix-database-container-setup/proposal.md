## Why

Alembic migrations cannot run inside Docker because: (1) `database/` directory is not mounted into any container, and (2) `alembic.ini` uses `%(DATABASE_URL)s` ConfigParser interpolation which conflicts with logging format strings and doesn't read env vars. This blocks all schema work starting from Phase 1.

## What Changes

- **[docker]** Mount `database/` as a volume in the `core-api` container
- **[database]** Fix `alembic.ini` to use a dummy `sqlalchemy.url` placeholder (env.py already overrides it from `os.environ["DATABASE_URL"]`)

## Non-Goals

- No changes to Alembic env.py or migration logic — those work correctly
- No new migration files or schema changes

## MVP Phase

Phase 0 bugfix (blocks Phase 1+)

## Capabilities

### New Capabilities
<!-- None — this is a bugfix -->

### Modified Capabilities
- `docker-dev-env`: Database volume mount added to core-api service
- `database-setup`: alembic.ini sqlalchemy.url config fixed

## Impact

- **Files:** `docker-compose.yml`, `database/alembic.ini`
- **Services:** core-api container gains access to `database/` directory
- **Migrations:** `alembic upgrade head` becomes runnable inside Docker
