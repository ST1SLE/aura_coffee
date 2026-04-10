## 1. Worker Dockerfile parity with core-api

- [x] 1.1 PREREQ [payment-worker] Edit `services/payment-worker/Dockerfile` — change `pip install --no-cache-dir /app/packages/shared` to `pip install --no-cache-dir -e /app/packages/shared` and similarly for `/app/services/payment-worker`.
- [x] 1.2 PREREQ [payment-worker] Add `FROM base AS dev` stage to `services/payment-worker/Dockerfile` with `RUN pip install --no-cache-dir -e "/app/services/payment-worker[dev]"`.
- [x] 1.3 PREREQ [sms-worker] Apply the same editable-install change to `services/sms-worker/Dockerfile`.
- [x] 1.4 PREREQ [sms-worker] Add the same `dev` target stage to `services/sms-worker/Dockerfile`.
- [x] 1.5 PREREQ [payment-worker] Add `[dev]` extras entry to `services/payment-worker/pyproject.toml` containing `pytest`, `pytest-asyncio` (mirror core-api's list) if not already present.
- [x] 1.6 PREREQ [sms-worker] Add `[dev]` extras entry to `services/sms-worker/pyproject.toml`.

## 2. docker-compose worker test affordances

- [x] 2.1 PREREQ [docker] Edit `docker-compose.yml` — add `target: dev` to the `payment-worker` service build block.
- [x] 2.2 PREREQ [docker] Edit `docker-compose.yml` — add `target: dev` to the `sms-worker` service build block.
- [x] 2.3 PREREQ [docker] Mount `./services/payment-worker/tests:/app/services/payment-worker/tests` in the `payment-worker` service volumes list (create the directory with a `.gitkeep` so the mount has a source).
- [x] 2.4 PREREQ [docker] Mount `./services/sms-worker/tests:/app/services/sms-worker/tests` in the `sms-worker` service volumes list (create directory + `.gitkeep`).

## 3. TEST_DATABASE_URL environment contract

- [x] 3.1 PREREQ [docker] Edit `.env.example` — add `TEST_DATABASE_URL=postgresql://aura:aura_secret@postgres:5432/aura_coffee_test` under a new `# Testing` section header.
- [x] 3.2 PREREQ [core-api] Edit `services/core-api/tests/conftest.py:9` — replace `_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")` with `_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")`. Removes the silent fallback to the production DB.

## 4. RED — tests for the new behavioral contract

- [x] 4.1 RED [core-api] Create `services/core-api/tests/test_migration_bootstrap.py::test_upgrade_head_without_admin_env_vars`. Assert: given a clean `aura_coffee_test` database and `ADMIN_LOGIN` / `ADMIN_PASSWORD` unset in `os.environ`, `alembic.command.upgrade(cfg, "head")` completes without raising. Currently fails at revision `0003` with `RuntimeError`.
- [x] 4.2 RED [core-api] Create `services/core-api/tests/test_migration_bootstrap.py::test_upgrade_head_no_admin_row_seeded`. Assert: after `command.upgrade(cfg, "head")` the `staff_accounts` table is empty. Currently fails — migration `0003` inserts an admin row.
- [x] 4.3 RED [core-api] Create `services/core-api/tests/test_seed_initial_admin.py::test_seed_creates_admin_row`. Assert: invoking `database.seeds.initial_admin.run()` against a migrated empty DB with `ADMIN_LOGIN=admin` and `ADMIN_PASSWORD=pw` inserts exactly one row with `login="admin"` and a bcrypt-hashed password. Currently fails — module does not exist.
- [x] 4.4 RED [core-api] Create `services/core-api/tests/test_seed_initial_admin.py::test_seed_is_idempotent`. Assert: invoking `run()` twice results in exactly one `staff_accounts` row (the second call uses `ON CONFLICT (login) DO NOTHING`). Currently fails — module does not exist.

## 5. GREEN — implement the seed module

- [x] 5.1 GREEN [database] Create `database/seeds/__init__.py` (empty package marker). Satisfies 4.3 import resolution.
- [x] 5.2 GREEN [database] Create `database/seeds/initial_admin.py` with `run()` function: read `ADMIN_LOGIN`/`ADMIN_PASSWORD` from env, `bcrypt.hashpw` the password, connect via `DATABASE_URL` (or `TEST_DATABASE_URL` if passed as arg), execute `INSERT INTO staff_accounts (...) VALUES (...) ON CONFLICT (login) DO NOTHING`. Also add `if __name__ == "__main__": run()` for CLI usage. Satisfies 4.3, 4.4.

## 6. MIGRATE — split admin seed out of migration 0003

- [x] 6.1 MIGRATE [database] Edit `database/migrations/versions/0003_staff_accounts.py` — remove the `import os`, `import uuid`, `import bcrypt`, `admin_login = os.environ.get(...)`, the `RuntimeError` guard, the `password_hash = bcrypt.hashpw(...)`, the `staff_table = sa.table(...)`, and the `op.bulk_insert(...)` call. Keep only the `CREATE TABLE`, `CREATE INDEX`, and the `downgrade()`. Satisfies 4.1, 4.2.
- [ ] 6.2 VERIFY [database] Run `docker compose exec core-api sh -c "cd /app/database && alembic downgrade base && alembic upgrade head"` with `ADMIN_LOGIN` and `ADMIN_PASSWORD` unset. Both commands SHALL succeed without error.

## 7. GREEN — conftest auto-provisions the test database

- [x] 7.1 GREEN [core-api] Edit `services/core-api/tests/conftest.py` — add a new session-scoped fixture `_ensure_test_database()` that runs before `migrated_db_session`. The fixture parses `_TEST_DB_URL`, connects to the `postgres` maintenance database with the same credentials via a new SQLAlchemy engine (`isolation_level="AUTOCOMMIT"`), runs `SELECT 1 FROM pg_database WHERE datname = 'aura_coffee_test'`, and executes `CREATE DATABASE aura_coffee_test` if the row is missing. Skips entirely if `_TEST_DB_URL` starts with `sqlite`.
- [x] 7.2 GREEN [core-api] Edit `migrated_db_session` in `conftest.py` — add `_ensure_test_database` as a dependency so creation always precedes `command.upgrade`.

## 8. VERIFY — end-to-end worktree flow

- [ ] 8.1 VERIFY [core-api] On a fresh Postgres volume (`docker compose down -v && docker compose up -d postgres redis`) with a `.env` copied verbatim from `.env.example`, run `docker compose exec core-api pytest services/core-api/tests/ -v`. All tests SHALL pass with zero skips due to missing `TEST_DATABASE_URL`.
- [ ] 8.2 VERIFY [payment-worker] Run `docker compose build payment-worker` (the `target: dev` is already declared in `docker-compose.yml`; there is no `--target` CLI flag on `docker compose build`) then `docker compose run --rm payment-worker python -c "import shared; print(shared.__file__)"`. The printed path SHALL point inside `/app/packages/shared/src`, confirming the editable install honors the volume mount.
- [ ] 8.3 VERIFY [sms-worker] Same check for sms-worker: `docker compose build sms-worker && docker compose run --rm sms-worker python -c "import shared; print(shared.__file__)"`.

## 9. Documentation — workflow visible to future agents

- [x] 9.1 PREREQ [database] Edit `database/AGENTS.md` — under the existing `## Testing` section, add:
  - `TEST_DATABASE_URL` contract (where it comes from, what the fixture does with it)
  - `env.py` placeholder rule (never overwrite a caller-provided URL)
  - Schema-only migration rule (no env var reads in `upgrade()`, seeds go to `database/seeds/`)
  - How to run `python -m database.seeds.initial_admin` manually
- [x] 9.2 PREREQ [core-api] Edit `services/core-api/AGENTS.md` — expand the `## Testing` section with:
  - Canonical command: `docker compose exec core-api pytest services/core-api/tests/ -v`
  - sqlite-default vs postgres-opt-in fixture split (`client` vs `migrated_db_session`)
  - Auto-provisioning of `aura_coffee_test` on first run
  - How to reset the test DB (`docker compose exec postgres dropdb -U aura aura_coffee_test`)
- [x] 9.3 PREREQ [root] Edit `AGENTS.md` — add a `### Worktree Testing Workflow` subsection under Development Methodology with a three-line summary: copy `.env.example` to `.env`, start the stack, run pytest; the test DB is auto-created. Link to `services/core-api/AGENTS.md` for details.
- [x] 9.4 PREREQ [openspec] Edit `openspec/config.yaml` — add four new entries to the `design:` list per Design D6:
  1. Editable installs for monorepo packages
  2. `dev` target + `target: dev` for services running tests
  3. Schema-only Alembic migrations, seeds under `database/seeds/`
  4. Test DB isolation via `TEST_DATABASE_URL` and `env.py` placeholder contract

## 10. Final verification

- [x] 10.1 VERIFY [openspec] Run `openspec validate fix-test-infra-worktree-safety --strict`. SHALL pass with no errors.
- [ ] 10.2 VERIFY [root] Re-run the full flow from 8.1 in a **second** worktree created via `git worktree add`. In the second worktree's `.env`, bump every host port by `+10` per section 11 (e.g. `POSTGRES_PORT=5443`, `REDIS_PORT=6389`, `CORE_API_PORT=8010`, `WEB_CUSTOMER_PORT=5183`, `WEB_ADMIN_PORT=5184`, `NGINX_PORT=90`) and update `CORS_ORIGINS` to match. Then `docker compose up -d` SHALL succeed without port collisions against the first worktree's stack, and `docker compose exec core-api pytest services/core-api/tests/ -v` SHALL pass.

## 11. Follow-up: per-worktree host port overrides

- [x] 11.1 PREREQ [docker] Parameterize every hardcoded host port in `docker-compose.yml` as `${VAR:-default}`. Added: `redis` (`REDIS_PORT`), `core-api` (`CORE_API_PORT`), `web-customer` (`WEB_CUSTOMER_PORT`), `web-admin` (`WEB_ADMIN_PORT`), `nginx` (`NGINX_PORT`). `postgres` already used `${POSTGRES_PORT:-5433}`.
- [x] 11.2 PREREQ [docker] Add a `# Host port bindings` section to `.env.example` listing all six port env vars with their defaults and a comment explaining the "pick an offset per worktree, apply to every port" convention.
- [x] 11.3 PREREQ [root] Document the multi-worktree port override pattern in `AGENTS.md` under the Worktree Testing Workflow subsection, including the `CORS_ORIGINS` gotcha (it hardcodes 5173/5174 and must be updated if web ports are bumped).
