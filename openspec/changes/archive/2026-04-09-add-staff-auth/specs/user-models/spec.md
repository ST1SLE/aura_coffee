## ADDED Requirements

### Requirement: Staff accounts table
The system SHALL create a `staff_accounts` table with columns: `id` (UUID PK, server-generated), `login` (VARCHAR, UNIQUE, NOT NULL), `password_hash` (VARCHAR, NOT NULL, bcrypt hash), `role` (ENUM `staff_role`: admin, barista, courier, NOT NULL), `display_name` (VARCHAR, NOT NULL), `is_active` (BOOLEAN, default true, NOT NULL), `created_at` (TIMESTAMPTZ, NOT NULL), `updated_at` (TIMESTAMPTZ, nullable). Index on `login` for O(1) lookup. Ref: PDD §5.1, §7.1 Phase 1 step 4.

#### Scenario: Staff account record created
- **WHEN** a staff account is inserted with login, password_hash, role, and display_name
- **THEN** `staff_accounts` row is created with `is_active` = true, `created_at` = now()

#### Scenario: Login uniqueness enforced
- **WHEN** attempt to create a second staff account with the same `login`
- **THEN** database rejects with unique constraint violation

#### Scenario: Role enum constraint
- **WHEN** attempt to insert a staff account with role not in (admin, barista, courier)
- **THEN** database rejects with enum constraint violation

### Requirement: StaffRole enum in shared package
The system SHALL define `StaffRole` enum in shared package with values: `ADMIN`, `BARISTA`, `COURIER`. The SQLAlchemy `Enum` column MUST use `values_callable` to map Python enum names to lowercase PostgreSQL enum values (e.g., `ADMIN` → `admin`). Ref: PDD §3, INV-010.

#### Scenario: Enum values match PDD roles
- **WHEN** `StaffRole` enum is inspected
- **THEN** it contains exactly three values: ADMIN, BARISTA, COURIER

#### Scenario: SQLAlchemy column maps to lowercase PostgreSQL values
- **WHEN** a `StaffAccount` record is inserted with `role=StaffRole.ADMIN`
- **THEN** PostgreSQL stores the value as `admin` (lowercase)

### Requirement: Alembic migration for staff accounts
The system SHALL create an Alembic migration that creates `staff_role` ENUM type, `staff_accounts` table, and seeds an initial admin account. Admin credentials (login, password) SHALL be read from environment variables `ADMIN_LOGIN` and `ADMIN_PASSWORD` (INV-015). Password SHALL be bcrypt-hashed at migration time. Migration SHALL be reversible. Ref: PDD §5.5, §7.1 Phase 1 step 4.

#### Scenario: Forward migration
- **WHEN** `alembic upgrade head` is run with `ADMIN_LOGIN` and `ADMIN_PASSWORD` env vars set
- **THEN** `staff_role` enum type, `staff_accounts` table, and initial admin account are created

#### Scenario: Rollback migration
- **WHEN** `alembic downgrade -1` is run
- **THEN** `staff_accounts` table and `staff_role` enum type are dropped cleanly

#### Scenario: Missing admin env vars
- **WHEN** migration runs without `ADMIN_LOGIN` or `ADMIN_PASSWORD` env vars
- **THEN** migration fails with a clear error message
