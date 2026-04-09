## ADDED Requirements

### Requirement: Alembic initialization
The `database/` directory SHALL contain a working Alembic setup with `alembic.ini` and `migrations/` directory. Alembic SHALL read `DATABASE_URL` from environment variables (INV-015).

#### Scenario: Alembic recognizes configuration
- **WHEN** a developer runs `alembic current` from `database/`
- **THEN** Alembic connects to the database and reports the current revision (or empty for a fresh database)

### Requirement: Initial migration
An initial Alembic migration SHALL exist that creates no tables but validates the migration pipeline works end-to-end. It SHALL be the base revision.

#### Scenario: Run initial migration on empty database
- **WHEN** a developer runs `alembic upgrade head` against an empty PostgreSQL database
- **THEN** Alembic applies the migration without errors and `alembic_version` table exists

#### Scenario: Downgrade initial migration
- **WHEN** a developer runs `alembic downgrade base`
- **THEN** the migration is reversed and the database returns to its pre-migration state

### Requirement: Autogenerate support
Alembic's `env.py` SHALL import SQLAlchemy models from the `shared` package so that `alembic revision --autogenerate` can detect model changes.

#### Scenario: Autogenerate detects new model
- **WHEN** a new SQLAlchemy model is added to `shared.models` and `alembic revision --autogenerate` is run
- **THEN** Alembic generates a migration file with the corresponding `CREATE TABLE` operation
