## Why

Phase 3 (Order & Payment) introduces 9 new database tables, 9 new enums, Pydantic schemas for orders and shop settings, and a new Alembic migration. TDD discipline (per project workflow) requires that we capture the spec as executable tests BEFORE any implementation, so the RED cycle delivers only failing tests that pin down the schema contract from PDD §5.2, §5.4, §6.1, and §6.2.

## What Changes

- Add `services/core-api/tests/test_models_order.py` — SQLAlchemy model tests (import checks, columns, types, nullability, defaults, FK/CASCADE behavior, immutability of `order_items`, UUID/int PK, Numeric for geo, TIMESTAMPTZ, JSONB).
- Add `services/core-api/tests/test_schemas_order.py` — Pydantic schema tests for `CreateOrderRequest`, `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `OrderStatusUpdate`, `CancelOrderRequest`, `RepeatOrderResult`, and `ShopSettingsResponse` (required vs optional fields, default values, nested shapes, enum acceptance).
- Add `services/core-api/tests/test_migration_0005_phase3_schema.py` — migration-level tests: upgrade creates 9 tables, indexes from PDD §5.4 exist (partial index on active orders, composite (user_id, created_at DESC), UNIQUE code, etc.), CHECK constraint `id=1` on `shop_settings`, and seed row for `shop_settings` matches the spec defaults.
- All new tests are expected to FAIL until the GREEN cycle lands implementation (models, schemas, migration, seed).

## Capabilities

### New Capabilities
- `order-schema-tests`: RED-cycle test suite that pins the Phase 3 schema contract (models + schemas + migration + seed) from PDD §5.2, §5.4, §6.1, §6.2 before any implementation exists. Lives in `services/core-api/tests/` and covers the 9 new tables, their enums, Pydantic DTOs, and the Alembic migration/seed.

### Modified Capabilities

## Impact

- Affected code: `services/core-api/tests/` (new test files only).
- Affected tooling: `pytest` test suite will include new failing tests (expected during RED).
- Affected dependencies: none — tests use existing pytest + SQLAlchemy + Alembic + Pydantic already in the project.
- Not affected in this cycle: production code under `packages/shared/src/shared/models/`, `packages/shared/src/shared/enums.py`, `database/migrations/`, `database/seeds/`, or `services/core-api/src/core_api/schemas/` — those ship in the GREEN cycle.

## MVP Phase

- Phase 3: Order & Payment (PDD §7.1).

## Non-Goals

- No production code changes (no new models, enums, schemas, migrations, or seed files).
- No API endpoints, routes, Celery tasks, or worker integrations.
- No YuKassa integration, webhook handling, or SMS flows.
- No Order/Payment/Refund state-machine logic (§6.1, §6.2 behavior tests are deferred to later RED cycles on business logic).
- No frontend work (customer/admin SPAs).
- No performance/load testing.
