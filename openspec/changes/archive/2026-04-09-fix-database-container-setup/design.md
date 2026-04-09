## Context

After `project-init-backend`, all services run in Docker but `alembic upgrade head` fails because:
1. `database/` is not copied into or mounted in any container
2. `alembic.ini` uses `%(DATABASE_URL)s` — ConfigParser interpolation, not env var substitution. It conflicts with `%(message)s` in the logging formatter section.

**Affected modules:** [database], [core-api] (docker-compose volume only)

## Goals / Non-Goals

**Goals:**
- `alembic upgrade head` SHALL work from inside the core-api container
- `alembic.ini` SHALL NOT use ConfigParser interpolation for the database URL

**Non-Goals:**
- No changes to `env.py` — it correctly reads `os.environ["DATABASE_URL"]`
- No separate database migration container — run migrations via `docker compose exec core-api`

## Decisions

### D1: Mount database/ into core-api only

Mount `./database:/app/database` as a volume in the core-api service. Core-api is the only service that needs to run migrations. Workers don't need Alembic access.

### D2: Dummy URL in alembic.ini

Set `sqlalchemy.url` to a dummy placeholder string. The `env.py` overrides this at runtime via `config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])`, so the ini value is never used. This avoids ConfigParser `%()s` interpolation conflicts.

## Risks / Trade-offs

- None — minimal config fix.
