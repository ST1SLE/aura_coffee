## Why

Fresh worktrees and new contributors hit the same tinfra papercuts every time:

1. `payment-worker` and `sms-worker` Dockerfiles install `packages/shared` **non-editable** (`pip install` instead of `pip install -e`). The `docker-compose.yml` volume mount on `./packages/shared/src` is therefore silently ignored by workers — they run stale copied code until a rebuild. Core-api works, workers drift. Guaranteed silent divergence.
2. `TEST_DATABASE_URL` is not in `.env.example`, so a clean `cp .env.example .env` leaves it unset. The `migrated_db_session` fixture (`services/core-api/tests/conftest.py:41`) then silently skips every Postgres-dependent test. Migration and model tests look green while actually running zero assertions.
3. Even when a developer sets `TEST_DATABASE_URL` manually, `aura_coffee_test` does not exist yet, and migration `0003_staff_accounts.py` crashes unless `ADMIN_LOGIN` and `ADMIN_PASSWORD` env vars are set — because it does `bulk_insert` of the admin user inside `upgrade()`. Data seeding in schema DDL couples tests to environment state and breaks fresh-worktree flows.
4. Workers have no `dev` build target and no `tests/` volume mount. The moment someone adds worker tests, they will rebuild and redebug the same Dockerfile gaps core-api already solved.
5. None of these lessons are encoded in `openspec/config.yaml` or the `AGENTS.md` files, so the next change can reintroduce them.

The goal is to make `docker compose exec core-api pytest` **just work** on a clean worktree — no manual DB creation, no env-var fiddling, no fixture skips — and to encode the rules so future changes cannot regress.

## What Changes

- **[payment-worker] [sms-worker]** Dockerfiles switch to `pip install -e` for monorepo packages and gain a `dev` target that installs `[dev]` extras.
- **[docker]** `docker-compose.yml` sets `target: dev` for both workers and mounts their `tests/` directories.
- **[docker]** `.env.example` gains `TEST_DATABASE_URL=postgresql://aura:aura_secret@postgres:5432/aura_coffee_test`.
- **[database]** Migration `0003_staff_accounts.py` becomes schema-only. The admin bulk-insert and `ADMIN_LOGIN`/`ADMIN_PASSWORD` env var reads move out of `upgrade()` into a new `database/seeds/001_initial_admin.py` runnable script.
- **[core-api]** `tests/conftest.py` auto-creates `aura_coffee_test` via a maintenance connection at session start, then runs `alembic upgrade head` against it. The `_TEST_DB_URL` fallback to `DATABASE_URL` is removed to eliminate any path to the production DB.
- **[openspec]** `config.yaml` gains four design rules enforcing editable installs, worker `dev` targets, schema-only migrations, and test DB isolation.
- **[docs]** `AGENTS.md` (root), `database/AGENTS.md`, and `services/core-api/AGENTS.md` document the worktree testing workflow so future agents inherit the contract.

## Non-Goals

- No new pytest plugins or test framework changes.
- No per-worktree `COMPOSE_PROJECT_NAME` isolation (docker-compose already derives project name from the worktree directory; distinct directories already get distinct containers). Running two worktrees with the stack up simultaneously still collides on the `5433` host port — one-at-a-time remains a known limitation.
- No worker test suites added. This change unblocks them; it does not write them.
- No second Postgres container for tests. `aura_coffee` and `aura_coffee_test` share the same instance on different databases.
- No refactor of existing core-api tests that already work against sqlite.

## MVP Phase

Phase 0 infrastructure hardening. Blocks reliable test-driven work in Phase 2 (Menu & Cart) and beyond.

## Capabilities

### Modified Capabilities
- `docker-dev-env`: worker Dockerfiles mandate editable installs and a `dev` target; worker test directories are volume-mounted.
- `database-setup`: migrations become schema-only; seed data is separated; `TEST_DATABASE_URL` is a first-class contract; `conftest.py` auto-provisions the test database.

### New Capabilities
_(none — both capabilities already exist)_

## Deviation from rule 63 (red/green split)

`openspec/config.yaml` rule 63 requires backend changes to split into `-red` and `-green` changes. This change is deliberately submitted as a single change because:

- Seven of the eleven tasks are PREREQ (Dockerfiles, compose, `.env.example`, docs, config.yaml) — rule 63 itself exempts PREREQ from TDD.
- The behavioral work (schema-only migration, seed script, conftest auto-provision) has three RED tests, three GREEN/MIGRATE implementations, and two VERIFY steps — not enough independent surface to justify two changes.
- Splitting would produce a `-red` change containing almost entirely PREREQ tasks and three tests, and a `-green` change with fewer than five tasks. The artifact overhead exceeds the review value.

The proposal below groups RED tasks before the GREEN/MIGRATE tasks they unblock, preserving the spirit of TDD within a single change.

## Impact

- **Files:**
  - `services/payment-worker/Dockerfile`
  - `services/sms-worker/Dockerfile`
  - `docker-compose.yml`
  - `.env.example`
  - `database/migrations/versions/0003_staff_accounts.py`
  - `database/seeds/__init__.py` (new)
  - `database/seeds/001_initial_admin.py` (new)
  - `services/core-api/tests/conftest.py`
  - `services/core-api/tests/test_migration_bootstrap.py` (new)
  - `services/core-api/tests/test_seed_initial_admin.py` (new)
  - `openspec/config.yaml`
  - `AGENTS.md`
  - `database/AGENTS.md`
  - `services/core-api/AGENTS.md`
- **Behavioral:** `alembic upgrade head` becomes runnable without `ADMIN_*` env vars. `pytest` auto-creates the test DB. Worker volume mounts become live. Future changes touching Dockerfiles, migrations, or test setup inherit four new linting rules via `config.yaml`.
- **Migrations:** `0003_staff_accounts.py` loses its data seeding. Existing deployments with a seeded admin row are unaffected (no DDL change). Fresh deployments must run `python -m database.seeds.initial_admin` once after `alembic upgrade head`.
