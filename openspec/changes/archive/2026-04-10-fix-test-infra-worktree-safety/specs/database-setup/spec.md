## ADDED Requirements

### Requirement: Schema-only migrations
Alembic migrations SHALL contain only schema changes (DDL: `CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`, `CREATE TYPE`, etc.). Data seeding — inserting, updating, or deleting rows for initial state — SHALL NOT occur inside `upgrade()` or `downgrade()`. Seed data SHALL live under `database/seeds/` as standalone Python scripts invoked independently of Alembic.

Migrations that read application-level environment variables (e.g. `ADMIN_LOGIN`, `ADMIN_PASSWORD`, API keys) SHALL NOT be accepted. Migrations MAY read `DATABASE_URL` via `env.py` and nothing else. This guarantees that `alembic upgrade head` is deterministic, runnable in CI without secret provisioning, and safe to execute on a fresh worktree with no manual env-var setup.

#### Scenario: Upgrade head without application env vars
- **WHEN** a developer runs `alembic upgrade head` against an empty database
- **AND** `ADMIN_LOGIN`, `ADMIN_PASSWORD`, and other application env vars are unset
- **THEN** Alembic applies every migration without raising, and the `staff_accounts` table exists but is empty

#### Scenario: Seed script runs independently
- **WHEN** a developer runs `python -m database.seeds.initial_admin` against a migrated database
- **AND** `ADMIN_LOGIN` and `ADMIN_PASSWORD` are set in the environment
- **THEN** a single admin row is inserted into `staff_accounts` with the bcrypt-hashed password

#### Scenario: Seed script is idempotent
- **WHEN** the initial-admin seed script is run twice with the same credentials
- **THEN** exactly one admin row exists in `staff_accounts` (the second invocation is a no-op via `ON CONFLICT (login) DO NOTHING`)

### Requirement: Test database isolation
The test suite SHALL use a separate PostgreSQL database from the development or production database. The test database URL SHALL be configured via the `TEST_DATABASE_URL` environment variable, which SHALL be declared in `.env.example` with a default of `postgresql://aura:aura_secret@postgres:5432/aura_coffee_test`.

Test configuration (`services/core-api/tests/conftest.py`) SHALL NOT fall back to `DATABASE_URL` if `TEST_DATABASE_URL` is unset. If `TEST_DATABASE_URL` is missing, tests SHALL fall back only to the in-memory sqlite URL (`sqlite://`), which cannot corrupt any persistent data. There SHALL be no code path by which test execution can write to the production database.

Alembic's `env.py` SHALL NOT overwrite a caller-provided `sqlalchemy.url` on the Alembic `Config` object. If the URL in `alembic.ini` is still the placeholder (`driver://user:pass@localhost/dbname`), `env.py` MAY substitute `os.environ["DATABASE_URL"]`. Otherwise it SHALL leave the caller-provided URL untouched, so test fixtures can direct migrations at `TEST_DATABASE_URL`.

#### Scenario: .env.example declares the test database
- **WHEN** a developer copies `.env.example` to `.env`
- **THEN** the resulting `.env` contains a `TEST_DATABASE_URL` line pointing at a database named `aura_coffee_test`

#### Scenario: Conftest has no fallback to DATABASE_URL
- **GIVEN** `TEST_DATABASE_URL` is unset and `DATABASE_URL` is set to a production URL
- **WHEN** `pytest` is invoked
- **THEN** the test suite uses `sqlite://` for any DB-backed fixture, never the production URL

#### Scenario: env.py honors caller-provided URL
- **GIVEN** a test fixture sets `config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)` before calling `command.upgrade(cfg, "head")`
- **WHEN** `env.py` runs
- **THEN** `env.py` does NOT overwrite the URL with `os.environ["DATABASE_URL"]`, and migrations run against `TEST_DATABASE_URL`

#### Scenario: Test modules single-source the URL lookup
- **GIVEN** a test module under `services/core-api/tests/` that needs `TEST_DATABASE_URL` (e.g. for a module-scoped Alembic config or a sqlite-skip guard)
- **WHEN** the module is loaded
- **THEN** it imports `_TEST_DB_URL` from `tests.conftest` rather than re-reading `os.environ.get("TEST_DATABASE_URL")`, so the fallback-trap fix in conftest propagates to every consumer

### Requirement: Test database auto-provisioning
The `migrated_db_session` fixture in `services/core-api/tests/conftest.py` SHALL create the `aura_coffee_test` database at session start if it does not already exist. Creation SHALL use a maintenance connection to the `postgres` administrative database on the same host, with `isolation_level="AUTOCOMMIT"`, and SHALL issue `CREATE DATABASE aura_coffee_test` only if `pg_database` does not already contain a row for it.

Auto-provisioning SHALL be skipped when `TEST_DATABASE_URL` resolves to a sqlite URL (the default fallback for contributors without Postgres running).

The fixture SHALL NOT drop the test database on teardown; per-test isolation is achieved via transaction rollback at the session level. State accumulated across sessions is acceptable; Alembic upgrades are idempotent.

#### Scenario: Fresh worktree runs tests with no manual setup
- **GIVEN** a fresh git worktree where `aura_coffee_test` has never been created
- **WHEN** a developer runs `docker compose up -d postgres redis && docker compose exec core-api pytest services/core-api/tests/ -v`
- **THEN** the test session creates `aura_coffee_test`, runs `alembic upgrade head` against it, and all tests pass with zero skips caused by missing test-DB configuration

#### Scenario: Subsequent runs are idempotent
- **WHEN** `pytest` is run a second time in the same worktree
- **THEN** the fixture detects the existing `aura_coffee_test`, skips creation, and proceeds directly to the migration upgrade step

#### Scenario: Sqlite fallback skips auto-provisioning
- **GIVEN** `TEST_DATABASE_URL` is unset (fallback to `sqlite://`)
- **WHEN** `pytest` is run
- **THEN** no connection to PostgreSQL is attempted and no `CREATE DATABASE` statement is issued

#### Scenario: Out-of-band Alembic runs still auto-provision
- **GIVEN** a test module (e.g. `test_migration_0004_menu_tables.py`) that declares its own Alembic `Config` fixture and calls `command.upgrade` directly
- **WHEN** the fixture is resolved
- **THEN** it depends on `_ensure_test_database` so `aura_coffee_test` is created before the out-of-band upgrade runs, even on a fresh worktree where no prior fixture has touched the DB
