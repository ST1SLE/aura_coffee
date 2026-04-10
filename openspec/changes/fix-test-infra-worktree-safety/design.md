## Context

Six tinfra issues were discovered during the menu-foundation implementation session (commit `15ff7ed "multiple fixes"` on branch `menu_cart`). Four and a half were fixed locally for core-api. This change completes the set, extends the fixes to workers, and encodes the rules so they cannot regress.

**Affected modules:** [payment-worker], [sms-worker], [core-api], [database], [docker]

## Goals / Non-Goals

**Goals:**
- `docker compose exec core-api pytest` on a fresh worktree SHALL succeed with no manual setup beyond `cp .env.example .env` and `docker compose up -d postgres redis`.
- `alembic upgrade head` SHALL succeed without any application-level env vars (`ADMIN_LOGIN`, `ADMIN_PASSWORD`, etc.). Only `DATABASE_URL` or a caller-provided `sqlalchemy.url` is required.
- Volume mounts on `./packages/shared/src` SHALL be honored at runtime by all backend services, not just core-api.
- Future Python services SHALL inherit the editable-install / `dev` target pattern via `openspec/config.yaml` rules.
- Future migrations SHALL be schema-only by default, with seed data in `database/seeds/`.
- Agents working on worktrees in the future SHALL find the testing workflow documented in `AGENTS.md` files, not reverse-engineered from conftest.

**Non-Goals:**
- No redesign of the test fixture topology. `migrated_db_session` stays module-scoped; sqlite fallback stays.
- No splitting of `docker-compose.yml` into a `docker-compose.test.yml` overlay. One compose file remains the source of truth.
- No CI pipeline changes. CI can pick up these improvements opportunistically.
- No backfill migration for existing dev databases. The admin row that migration `0003` previously inserted persists in place after the DDL change.

## Decisions

### D1: Editable install for all monorepo packages in all Python Dockerfiles

`pip install /app/packages/shared` copies the source tree into `site-packages` at build time. The runtime volume mount on `./packages/shared/src:/app/packages/shared/src` then has no effect — Python still imports from the copied `site-packages` directory. `pip install -e` creates a `.pth` file pointing at the source directory, so the volume mount becomes live.

Core-api already does this. Workers do not. The fix is one-line-per-Dockerfile:

```dockerfile
# Before
RUN pip install --no-cache-dir /app/packages/shared

# After
RUN pip install --no-cache-dir -e /app/packages/shared
```

The same applies to the service's own package (`payment_worker`, `sms_worker`). This matters less today because workers don't live-reload, but it is free and keeps the pattern consistent.

**Encoded as config.yaml rule** so future Dockerfiles inherit it.

### D2: `dev` target on all backend Dockerfiles

Core-api has `FROM base AS dev` which installs `[dev]` extras (pytest and friends). Workers do not — running `pytest` inside a worker container currently requires a rebuild or a manual `pip install pytest`. Add the target now so that when worker tests land they are a compose flag away, not an infra yak.

```dockerfile
FROM base AS dev
RUN pip install --no-cache-dir -e "/app/services/payment-worker[dev]"
```

`docker-compose.yml` then sets `target: dev` on both workers and mounts `./services/<worker>/tests`. The production images built without `target: dev` remain lean.

**Encoded as config.yaml rule** so workers don't quietly regress when a future change rewrites their Dockerfiles.

### D3: Split data seeding out of Alembic migrations

Migration `0003_staff_accounts.py` currently does:

```python
admin_login = os.environ.get("ADMIN_LOGIN")
admin_password = os.environ.get("ADMIN_PASSWORD")
if not admin_login or not admin_password:
    raise RuntimeError(...)
op.bulk_insert(staff_table, [...])
```

Three consequences:
1. Every test that runs `alembic upgrade head` must set `ADMIN_LOGIN` / `ADMIN_PASSWORD` or the migration crashes.
2. CI must set them too.
3. Fresh worktrees fail mysteriously until the developer reads the migration file.

**The root cause is category confusion**: DDL is deterministic and environment-free; seed data is environment-dependent and may differ per deployment. Conflating them couples test and CI infrastructure to runtime secrets.

The fix is a clean split:
- `0003_staff_accounts.py` keeps only the `CREATE TABLE` and `CREATE INDEX`. No env var reads, no `bulk_insert`.
- `database/seeds/001_initial_admin.py` is a standalone script: reads `ADMIN_LOGIN`/`ADMIN_PASSWORD`, connects via `DATABASE_URL`, inserts the admin row with `ON CONFLICT (login) DO NOTHING` so it is idempotent.

Fresh deployment flow becomes:
```bash
alembic upgrade head                           # schema
python -m database.seeds.initial_admin         # seed
```

Existing deployments are unaffected — the admin row they already have persists, and the revised migration is a no-op for them.

**Encoded as config.yaml rule** so future migrations don't smuggle data seeding back into `upgrade()`.

### D4: `TEST_DATABASE_URL` in `.env.example`, remove the fallback trap in conftest

Current `conftest.py:9`:
```python
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
```

If `TEST_DATABASE_URL` is unset, tests silently fall back to `DATABASE_URL` — which in a running Docker environment points at `aura_coffee`, the production DB. A test that commits (or a migration test that downgrades) can corrupt real data.

After this change:
- `.env.example` declares `TEST_DATABASE_URL=postgresql://aura:aura_secret@postgres:5432/aura_coffee_test` so any `.env` copied from it has it set.
- `conftest.py` reads `TEST_DATABASE_URL` with a sqlite fallback (not a `DATABASE_URL` fallback): `_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")`.
- There is no code path from test execution to the production database. Ever.

**Encoded as config.yaml rule:** tests MUST use a separate database; `env.py` MUST honor caller-provided `sqlalchemy.url`.

### D5: Auto-provision the test database in the fixture

Setting `TEST_DATABASE_URL` is not enough — the database must exist before Alembic can connect. Options considered:

| Option | Pros | Cons |
|---|---|---|
| Manual `createdb` one-off | Zero code | Defeats the "just works" goal |
| Init script on the postgres container | Runs once automatically | Only runs on first-ever volume creation; fragile |
| Conftest fixture creates DB if missing | Explicit, idempotent, runs every session | ~10 lines of new code |
| Dedicated postgres-test container | Full isolation | Doubles RAM and startup time |

**Chosen:** conftest fixture creates the DB if missing. At session start, open a maintenance connection to the `postgres` admin database on the same host (parsed from `TEST_DATABASE_URL`), issue `CREATE DATABASE aura_coffee_test` inside a check-exists block, close the connection, then proceed with the existing `command.upgrade(cfg, "head")` flow. The fixture is already session-scoped as `migrated_db_session`; the new logic runs once per pytest session.

Idempotent: subsequent runs find the DB exists and skip creation. Migrations run every session (cheap, idempotent upgrades).

### D6: `openspec/config.yaml` design rule additions

Four rules added to the `design` section:

1. **Editable installs:** Python service Dockerfiles MUST install monorepo packages (`packages/*`) with `pip install -e`. Non-editable installs copy source into `site-packages` and silently break volume mounts.
2. **Dev targets:** Python service Dockerfiles SHOULD provide a `dev` target installing `[dev]` extras. `docker-compose.yml` MUST use `target: dev` for any service that runs tests.
3. **Schema-only migrations:** Alembic migrations MUST be schema-only (DDL). Data seeding MUST live under `database/seeds/` and run independently. Migrations requiring runtime env vars break CI and fresh worktrees.
4. **Test DB isolation:** Tests MUST use a separate database configured via `TEST_DATABASE_URL`. `database/migrations/env.py` MUST NOT overwrite a caller-provided `sqlalchemy.url`.

These are guardrails for every future `propose` invocation. They do not change existing specs.

### D7: Testing workflow documented in three `AGENTS.md` files

Agents that enter the repo in a fresh worktree should find the testing workflow in the first file they read, not in conftest internals:

- **Root `AGENTS.md`** — one paragraph under "Development Methodology" pointing at the worktree testing flow and the `TEST_DATABASE_URL` convention.
- **`services/core-api/AGENTS.md`** — the Testing section is expanded with concrete commands (`docker compose exec core-api pytest`), the sqlite-vs-postgres fixture split, and the auto-provisioning behavior.
- **`database/AGENTS.md`** — new "Testing" subsection documents the `env.py` placeholder contract, the seed separation rule, and how to run the initial admin seed.

## Risks / Trade-offs

- **Existing dev DBs with admin seeded via old migration** — unaffected. The DDL is unchanged; only the in-upgrade seed is removed. `alembic current` stays on `0004`.
- **Downgrade–upgrade cycles on existing dev DBs** — `alembic downgrade 0002 && alembic upgrade head` will no longer re-seed the admin. Developers must run the seed script after. Documented in `database/AGENTS.md`.
- **Stale `pip install` caches in partial rebuilds** — first `docker compose build` after this change must rebuild worker images. Cheap (under a minute).
- **`CREATE DATABASE` permissions** — the conftest maintenance connection uses the same credentials as the app. In local dev these are superuser. In CI they must be granted `CREATEDB`. Documented in the `AGENTS.md` update.
- **Test DB reuse across sessions** — the fixture does not drop the test DB on teardown. State accumulates until the developer drops it manually or a migration invalidates it. Acceptable for dev ergonomics; the session-scoped transaction rollback contains most test writes.

## Atomicity & State Machines

No financial operations. No state machine transitions. `INV-004` and `INV-016` not implicated.

## PII / 152-FZ

No PII handling changes. Test DB contains the same schema as production but no real customer data. `INV-013` not implicated. The admin seed script still reads `ADMIN_PASSWORD` from env and hashes with bcrypt — `INV-015` preserved.

## Migration Strategy

- **Forward:** update migration `0003` file in place (remove `bulk_insert` and env var reads). Rollback plan: the revised migration's `downgrade()` is unchanged (drops table + enum), so `alembic downgrade -1` works as before.
- **Data backfill:** none required. The admin row in existing deployments persists because the DDL is unchanged.
- **Verification:** `alembic downgrade base && alembic upgrade head` on a fresh DB with no env vars SHALL succeed. This is a VERIFY task.
