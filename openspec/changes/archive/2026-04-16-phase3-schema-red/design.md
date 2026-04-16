## Context

Phase 3 (Order & Payment) introduces the bulk of Aura Coffee's financial data model. Nine new tables, nine new enums, two Pydantic module files, one Alembic migration (0005) and one seed script for singleton shop settings need to land. Per the project's Two-Change Model (see `AGENTS.md` → "Development Methodology: TDD"), we split Phase 3 schema delivery into two OpenSpec changes on the same feature branch `feat/phase3-schema`:

1. `phase3-schema-red` (this change) — all tests exist and FAIL. No production code touched.
2. `phase3-schema-green` — implementation; the same test suite turns green.

Authoritative spec: PDD §5.2 (tables), §5.4 (indexes), §6.1 (order lifecycle — informs statuses/columns like `cancelled_by`, `cancelled_at`, `auto_completed`), §6.2 (payment lifecycle — informs payment/refund statuses).

Current state before this change:

- `packages/shared/src/shared/enums.py` has only `UserStatus`, `OTPStatus`, `StaffRole`, `CategoryType`, `MenuItemAvailability`, `SizeLabel`. None of the Phase 3 enums exist yet.
- `packages/shared/src/shared/models/__init__.py` registers `User`, `UserProfile`, `LoyaltyAccount`, `StaffAccount`, `Category`, `MenuItem`, `Modifier`, `SizeOption`. None of the Phase 3 models exist.
- `database/migrations/versions/` ends at `0004_menu_tables.py`. Migration `0005_phase3_schema.py` does not exist.
- `services/core-api/src/core_api/schemas/` has `auth`, `cart`, `menu`, `profile`, `staff_auth`. No `order` or `shop_settings` schema modules yet.
- `services/core-api/tests/conftest.py` provides `_ensure_test_database`, `migrated_db_session`, `db_session`, `_pg_ready`, and in-memory SQLite fallback with `TEST_DB_URL` detection. Tests that require PostgreSQL (migration + DDL features like JSONB, partial indexes, CHECK enforcement, `timezone=True`) MUST skip when `_TEST_DB_URL.startswith("sqlite")`. Model-level introspection tests (column names, FK targets, enum types declared on the mapper) work against the SQLite in-memory engine and MUST NOT skip.

Stakeholders: the RED suite is the interface contract. The GREEN cycle agent reads it to know what to build; human reviewers read it to verify PDD conformance before implementation work lands.

Affected modules: **[core-api]** (tests only), **[shared]** (target of imports — not mutated in RED), **[database]** (target of migration test — not mutated in RED).

## Goals / Non-Goals

**Goals:**
- RED suite MUST cover all 9 new tables, their columns, PK types, FK behavior (CASCADE where specified), nullability, defaults, JSONB shapes, Numeric fields, TIMESTAMPTZ columns, and enum types on the ORM mappers.
- RED suite MUST assert the 7 indexes listed in PDD §5.4 relevant to Phase 3 (order history, active-orders partial, `(type, status)`, promocode UNIQUE, `promocode_usages(promocode_id, user_id)`, loyalty history, notifications history).
- RED suite MUST assert the `CHECK (id = 1)` singleton constraint on `shop_settings`.
- RED suite MUST assert shop_settings seed defaults (Moscow coords, 5km radius, 50000/150000/20000 kopeck thresholds, 5% loyalty, 15 min prep, 30 min delivery, Mon–Sun 08:00–22:00 hours).
- RED suite MUST assert 9 new Pydantic schemas (`CreateOrderRequest`, `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `OrderStatusUpdate`, `CancelOrderRequest`, `RepeatOrderResult`, `ShopSettingsResponse`).
- All test files MUST be importable by `pytest`. Tests that would otherwise error on collection (because targets don't exist yet) MUST do their imports INSIDE the test function body so only the individual test fails, not the whole module.

**Non-Goals:**
- Production code in `packages/shared/`, `services/core-api/src/`, `database/migrations/versions/`, or `database/seeds/` — those are GREEN.
- API endpoints, routers, or services.
- YuKassa, SMS.ru, or any external-service interaction tests.
- Order/Payment state-machine transition tests (§6.1, §6.2 behavior) — those are deferred to a later RED cycle on business logic.
- Web/admin/customer frontend.
- Performance or concurrency tests.

## Decisions

### D1 — Test file layout mirrors existing Phase-2 patterns

**Decision:** Three test files, each named to match the implementation they pin down:
- `services/core-api/tests/test_models_order.py` — pins the 9 SQLAlchemy models.
- `services/core-api/tests/test_schemas_order.py` — pins Pydantic schemas for order + shop_settings.
- `services/core-api/tests/test_migration_0005_phase3_schema.py` — pins migration 0005 and shop_settings seed.

**Why X over Y:** Same layout as `test_models_menu.py`, `test_schemas_menu.py`, `test_migration_0004_menu_tables.py`. Alternative considered — a single combined file — rejected because: (a) review diff readability, (b) failure localization, (c) the migration tests need a module-scoped `alembic_cfg` fixture separate from the mapper-introspection and schema-validation tests.

### D2 — Model-mapper introspection tests run on SQLite in-memory

**Decision:** Column existence, column types (approximate — e.g. `Integer` vs `BigInteger` not strictly enforced), FK targets, mapper-declared enum names, and `__tablename__` assertions run against the SQLite in-memory engine already set up in `conftest.py`. These tests DO NOT skip.

**Why X over Y:** This catches model-definition mistakes immediately and runs anywhere (CI with or without Postgres). Alternative — require Postgres for all model tests — rejected because the `conftest.py` sqlite path is the default fallback and the existing `test_models_menu.py` tests follow this pattern.

### D3 — DDL-level assertions (JSONB, partial index WHERE clause, CHECK, TIMESTAMPTZ) require PostgreSQL

**Decision:** Any test that inspects reflected column types for `JSONB`, reads `pg_type` / `pg_constraint`, verifies `postgresql_where` predicates, tries to violate a CHECK, or asserts TIMESTAMPTZ marker MUST `@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")`. These tests use the existing `migrated_engine` fixture style from `test_migration_0004_menu_tables.py`.

**Why X over Y:** SQLite lacks JSONB, partial indexes with `WHERE`, enforced CHECK on INSERT for some expressions, and its `TIMESTAMP` equivalent doesn't carry timezone info. Trying to emulate in SQLite would give false positives.

### D4 — Imports inside test bodies (RED-safe collection)

**Decision:** All `from shared.models.* import ...`, `from core_api.schemas.order import ...`, etc. go INSIDE the test function, not at module top. Module-top imports stay limited to pytest, sqlalchemy, pydantic.

**Why X over Y:** In the RED cycle, those modules don't exist. If the import is at module top, pytest collection fails entirely and the whole file errors out instead of reporting N individual failures. Mirrors the pattern in `test_schemas_menu.py` and `test_models_menu.py`.

### D5 — UUIDs as PKs, enums stored as lowercase string values

**Decision:** Tests assert that `orders.id`, `order_items.id`, `payments.id`, `refunds.id`, `loyalty_transactions.id`, `promocodes.id`, `promocode_usages.id`, `notifications.id` are UUID columns. `shop_settings.id` is an integer (singleton, always 1). Tests assert enum PG type names in snake_case (`order_status`, `order_type`, `payment_status`, `refund_status`, `notification_channel`, `notification_type`, `notification_status`, `loyalty_transaction_type`, `promocode_discount_type`) with lowercase values (e.g. `order_status` values = `["created", "paid", "preparing", "ready", "in_delivery", "completed", "cancelled"]`).

**Why X over Y:** The existing convention (see `test_migration_0004_menu_tables.py`, which reads `pg_enum` and expects `["drink", "food", "merch", "modifier"]` — lowercase) forces lowercase values. `CategoryType` in `enums.py` mirrors this. Phase 3 MUST follow the same convention so existing migration and enum patterns work unchanged.

### D6 — Seed tests assert values, not just row existence

**Decision:** `test_migration_0005_phase3_schema.py` includes a seed test that, after running `alembic upgrade head` AND applying the `database/seeds/shop_settings.py` seed (the GREEN cycle will provide the seed script — RED asserts its end state), the single `shop_settings` row has `id = 1`, `shop_lat = 55.7558`, `shop_lon = 37.6173`, `delivery_radius_km = 5`, `min_delivery_amount = 50000`, `free_delivery_threshold = 150000`, `delivery_fee = 20000`, `loyalty_percent = 5`, `default_prep_time_minutes = 15`, `estimated_delivery_time_minutes = 30`, and `working_hours` JSONB contains the 7 weekday keys `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` each with `open: "08:00"`, `close: "22:00"`.

**Why X over Y:** "Row exists" passes trivially with any value. Asserting exact defaults pins the business contract. Rules from `database/AGENTS.md` forbid putting seed data in the migration itself — so the test invokes `database.seeds.shop_settings.run(TEST_DB_URL)` after `alembic upgrade head`. If the seed module doesn't exist yet (RED cycle), the import fails and the test fails — exactly what RED requires.

### D7 — Schema tests use `model_validate` with `SimpleNamespace` mocks for ORM round-trips

**Decision:** `OrderResponse.model_validate(namespace_like_order_row)` and `ShopSettingsResponse.model_validate(namespace_like_settings_row)` use `types.SimpleNamespace` as the ORM stand-in (same pattern as `test_schemas_menu.py`). `CreateOrderRequest` is tested with dict literals for positive/negative cases.

**Why X over Y:** Consistent with existing test style in the project. Avoids spinning up a DB session for schema-only tests.

## Risks / Trade-offs

- [Risk] SQLite-fallback CI might silently skip the migration tests → the RED suite appears "passing" (all-skipped) for contributors without Postgres. → Mitigation: document in each file's module docstring that migration tests skip on SQLite, match the existing pattern from `test_migration_0004_menu_tables.py`. The full suite in Docker always hits Postgres.
- [Risk] Asserting exact enum value strings pins them early; a future PDD amendment to values would force rework. → Mitigation: values are drawn directly from PDD §5.2/§6.1/§6.2, which is authoritative. If PDD changes, tests are the first thing to update.
- [Risk] The seed test depends on a seed script that GREEN will write at `database/seeds/shop_settings.py`. If GREEN chooses a different module path, the test breaks. → Mitigation: fix the path in this design (`database/seeds/shop_settings.py`, function `run(database_url)`) so GREEN has a firm target. Matches the convention of `database/seeds/initial_admin.py`.
- [Trade-off] Model-mapper introspection asserts "column exists and has a FK to X" rather than deep type equality. This accepts `BigInteger vs Integer` or `String(120) vs Text` drift at the model level — but migration tests catch DDL-level type drift. Acceptable: model tests prove structure, migration tests prove DDL.

## Migration Plan

The RED change adds only test files. No schema migration, no data migration, no rollback concern for this change specifically. Forward-only diff:
- `+ services/core-api/tests/test_models_order.py`
- `+ services/core-api/tests/test_schemas_order.py`
- `+ services/core-api/tests/test_migration_0005_phase3_schema.py`

Rollback strategy: `git revert` the commit or delete the three files. No production code touched, so zero operational risk.

## 152-FZ Compliance

This change touches test code only. No PII is stored or processed. The underlying models covered by these tests (to be written in GREEN) MUST continue referring to customers by `user_id` (UUID) only — `orders`, `payments`, `loyalty_transactions`, `notifications`, `promocode_usages` reference `users` by opaque ID, with no name/phone fields duplicated (INV-013). RED tests verify this by asserting the absence of PII columns (phone, name, address text) on these tables; only `delivery_address_snapshot` is allowed as a JSONB snapshot to preserve delivery history post-account-deletion — the snapshot becomes opaque data when its source PII is anonymized.

## Atomicity Analysis

Not applicable to this RED change — no runtime financial logic is tested here. INV-004 atomicity is enforced by the order-creation pipeline, which is out of scope for Phase 3 schema. Future RED cycles on business logic MUST include atomicity tests for points + promocode + payment.

## Open Questions

- None identified. All schema contracts are fully specified in PDD §5.2, §5.4, §6.1, §6.2 and the task brief. If the GREEN-cycle agent hits ambiguity, it is instructed to ASK rather than guess (per the worktree rules).
