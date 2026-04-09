## ADDED Requirements

### Requirement: Users table
The system SHALL create a `users` table with columns: `id` (UUID PK, server-generated), `phone_hash` (VARCHAR, UNIQUE, SHA-256 hex digest), `status` (ENUM: pending_verification, active, blocked, deleted per §6.5), `created_at` (TIMESTAMPTZ), `deleted_at` (TIMESTAMPTZ, nullable). Index on `phone_hash` for O(1) lookup.

#### Scenario: User record created
- **WHEN** a new user registers via OTP flow
- **THEN** `users` row is created with `phone_hash` = SHA-256 of normalized E.164 phone, `status` = pending_verification, `created_at` = now()

#### Scenario: Phone hash uniqueness enforced
- **WHEN** attempt to create a second user with the same `phone_hash`
- **THEN** database rejects with unique constraint violation

### Requirement: User profiles table with PII isolation
The system SHALL create a `user_profiles` table with columns: `user_id` (UUID FK→users, PK), `phone` (BYTEA, AES-256-GCM encrypted), `display_name` (VARCHAR, nullable), `preferred_language` (VARCHAR, default 'ru', values: 'ru'/'en'). This table is isolated from order data per INV-013 and 152-ФЗ compliance.

#### Scenario: Profile created with encrypted phone
- **WHEN** user record is created
- **THEN** `user_profiles` row is created with `phone` encrypted using AES-256-GCM with key from `ENCRYPTION_KEY` env var and unique nonce per record

#### Scenario: Phone decryption
- **WHEN** system needs plaintext phone (e.g., for SMS sending)
- **THEN** it decrypts `user_profiles.phone` using the same `ENCRYPTION_KEY`

### Requirement: Loyalty accounts table
The system SHALL create a `loyalty_accounts` table with columns: `user_id` (UUID FK→users, PK), `balance` (INTEGER, default 0, stored in points), `created_at` (TIMESTAMPTZ). Created only when user transitions to ACTIVE (§6.5).

#### Scenario: Loyalty account created on activation
- **WHEN** user status transitions from PENDING_VERIFICATION to ACTIVE
- **THEN** `loyalty_accounts` row is created with `balance` = 0

#### Scenario: Loyalty account not created for pending user
- **WHEN** user is in PENDING_VERIFICATION status
- **THEN** no `loyalty_accounts` row exists for this user

### Requirement: UserStatus enum in shared package
The system SHALL define `UserStatus` enum in shared package with values: `PENDING_VERIFICATION`, `ACTIVE`, `BLOCKED`, `DELETED` (§6.5). This enum SHALL be used by SQLAlchemy models and Pydantic schemas. The SQLAlchemy `Enum` column MUST use `values_callable` to map Python enum names to lowercase PostgreSQL enum values (e.g. `PENDING_VERIFICATION` → `pending_verification`).

#### Scenario: Enum values match PDD
- **WHEN** `UserStatus` enum is inspected
- **THEN** it contains exactly four values matching §6.5 states

#### Scenario: SQLAlchemy column maps to lowercase PostgreSQL values
- **WHEN** a `User` record is inserted with `status=UserStatus.PENDING_VERIFICATION`
- **THEN** PostgreSQL stores the value as `pending_verification` (lowercase)

### Requirement: Alembic migration for auth tables
The system SHALL create an Alembic migration that creates `users` table (with `user_status` ENUM type created implicitly via `create_table`), `user_profiles` table, `loyalty_accounts` table, and required indexes. The ENUM type MUST NOT be created explicitly before `create_table` to avoid duplicate type errors. Migration SHALL be reversible (up/down) per §5.5.

#### Scenario: Forward migration
- **WHEN** `alembic upgrade head` is run
- **THEN** all three tables and the enum type are created with correct constraints and indexes

#### Scenario: Rollback migration
- **WHEN** `alembic downgrade -1` is run
- **THEN** all three tables and the enum type are dropped cleanly

### Requirement: Phone normalization
The system SHALL normalize all phone numbers to E.164 format (`+7XXXXXXXXXX`) before hashing or encryption. Invalid phone formats SHALL be rejected with HTTP 422.

#### Scenario: Valid Russian phone number
- **WHEN** phone `+79161234567` is submitted
- **THEN** system normalizes to `+79161234567` and proceeds

#### Scenario: Phone with 8 prefix
- **WHEN** phone `89161234567` is submitted
- **THEN** system normalizes to `+79161234567` and proceeds

#### Scenario: Invalid phone format
- **WHEN** phone `12345` is submitted
- **THEN** system returns HTTP 422 with validation error

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
