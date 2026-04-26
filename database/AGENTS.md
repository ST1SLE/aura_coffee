# Database

Alembic migrations and seed data for PostgreSQL — the single source of truth for all persistent data.

**PDD sections:** §5 (Data Storage Strategy), §5.1 (Principles), §5.2 (Table groups), §5.4 (Indexes), §5.5 (Migrations)

## Tech Stack

- Alembic (migrations)
- SQLAlchemy 2.0 for migration scripts
- PostgreSQL 16

## Scope

This module is responsible for:
- Schema migrations (table creation, alterations, index management)
- Seed data (initial shop settings, admin account, test data for development)
- Index definitions (see §5.4 for required indexes)

## Constraints

- **Migrations MUST be idempotent and reversible** (up/down) per §5.5. Every migration has a rollback.
- **Destructive migrations via two-phase process:** Add new column → migrate data → remove old column. No downtime.
- **Prices in kopecks (INTEGER).** All monetary values are stored as integers representing kopecks. No FLOAT, no DECIMAL for money.
- **Timestamps in UTC (`TIMESTAMPTZ`).** All tables include `created_at` and `updated_at` in UTC.
- **PII isolation (INV-013):** `user_profiles` and `delivery_addresses` are separate from `orders`/`payments`. Tables reference users by opaque `user_id` (UUID). Phone stored encrypted (AES-256-GCM), phone_hash (SHA-256) for lookup.
- **Immutable order items (INV-014):** `order_items` table MUST NOT have UPDATE or DELETE operations. Schema should enforce this via application-level constraints (DB triggers if needed).
- **Soft delete (§5.1):** Users are soft-deleted via `deleted_at` + anonymization. Menu items use `archived = true`. Physical DELETE on business tables is FORBIDDEN.
- **Singleton shop_settings:** Always 1 row, `CHECK (id = 1)`. Updated via UPDATE, not INSERT.

## Table Groups

Reference PDD §5.2 for full schema. Groups:
- Users: `users`, `user_profiles`, `delivery_addresses`, `staff_accounts`
- Menu: `categories`, `menu_items`, `size_options`, `modifiers`, `menu_item_modifiers`
- Orders: `orders`, `order_items`
- Payments: `payments`, `refunds`
- Loyalty: `loyalty_accounts`, `loyalty_transactions`
- Promocodes: `promocodes`, `promocode_usages`
- Notifications: `notifications`
- Settings: `shop_settings`

## Key Files

_(to be updated as code is added)_

## Testing

- **Framework:** Alembic CLI
- **Validation:** every migration MUST be verified with `alembic upgrade head` + `alembic downgrade -1` (or full downgrade)
- **No unit tests** — migrations are validated by running them, not by pytest
- **Methodology:** GRACE substrate does not apply to Alembic version files (immutable historical snapshots). MIGRATE → VERIFY pattern remains: run `alembic upgrade head` and `alembic downgrade -1` to verify each new migration. Seed scripts in `database/seeds/*.py` carry GRACE contracts; migration version files do not.

### Test database contract

- Tests use a **separate** database, `aura_coffee_test`, addressed by `TEST_DATABASE_URL` (declared in `.env.example`). Tests MUST NEVER run against `DATABASE_URL`.
- `database/migrations/env.py` checks whether `sqlalchemy.url` has been set by the caller. If it has (test fixtures do this), `env.py` does NOT overwrite it with `os.environ["DATABASE_URL"]`. This is how Alembic commands get redirected at the test DB.
- The test DB is auto-created by `services/core-api/tests/conftest.py::_ensure_test_database` on first run — no manual `createdb` needed on fresh worktrees.

### Schema-only migrations

- Migrations MUST contain only DDL (`CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`, `CREATE TYPE`).
- **No `op.bulk_insert`, no environment variable reads, no API calls.** Seed data lives under `database/seeds/` as standalone scripts.
- Reason: migrations that depend on runtime env vars break CI, tests, and fresh worktrees. The old `0003_staff_accounts` bug (required `ADMIN_LOGIN`/`ADMIN_PASSWORD` inside `upgrade()`) is the anti-pattern to avoid.

### Running the initial admin seed

The `db-seed` compose service runs `python -m database.seeds.initial_admin` automatically on every `docker compose up`, after `db-migrate` completes. No manual step is needed.

`ADMIN_LOGIN` and `ADMIN_PASSWORD` are read from `.env`; dev defaults (`admin` / `admin123`) are committed in `.env.example`. Override them in your `.env` for any non-dev environment. The script inserts one row into `staff_accounts` with `ON CONFLICT (login) DO NOTHING` (idempotent).

## This Module MUST NOT

- Contain application logic (that's core-api)
- Define API schemas or route handlers
- Include seed data with real customer information
- Use FLOAT or DECIMAL for monetary values
