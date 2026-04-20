## Why

PDD §3 lists "Delivery Address" as a first-class domain entity and §5.2 pins the `delivery_addresses` table (`user_id`, `label`, `address_text`, `lat`, `lon`, `apartment`, `entrance`, `floor`, `comment`, `is_default`). Today only the `delivery_address_snapshot` JSONB column on `orders` exists — customers must re-enter their address on every delivery checkout. Phase 4 (Delivery) in PDD §7.1 requires saved addresses so returning customers can pick one and skip re-geocoding. TDD discipline (AGENTS.md §Two-Change Model) requires the RED cycle to pin the contract as failing tests before any code is written.

## What Changes

- Add `services/core-api/tests/test_delivery_addresses_api.py` — HTTP tests for the new CRUD router `/api/v1/profile/addresses` (auth=customer):
  - `GET  /api/v1/profile/addresses` — list current user's saved addresses.
  - `POST /api/v1/profile/addresses` — create; server-side Haversine radius validation against `ShopSettings` (PDD §7.3 step 3); 422 on out-of-radius; 422 on malformed body; 201 on happy path with body echoing the created row including UUID.
  - `PATCH /api/v1/profile/addresses/{address_id}` — partial update; setting `is_default=true` atomically demotes the previous default (only one row per user may have `is_default=true`).
  - `DELETE /api/v1/profile/addresses/{address_id}` — delete own address.
  - Ownership: for `PATCH`/`DELETE`, a foreign `address_id` MUST return `404` (NOT `403`) — do not leak existence of another user's row.
  - RBAC: staff roles (`admin`/`barista`/`courier`) receive `403`; unauthenticated requests receive `401`.
  - RBAC matrix coverage: assert the four routes appear in `ROUTE_MATRIX` with value `{CUSTOMER}` exactly.
- Add `services/core-api/tests/test_checkout_delivery_address_id.py` — tests that extend the checkout contract:
  - `CreateOrderRequest` MUST accept an optional `delivery_address_id: UUID | None` field.
  - XOR rule for `type=DELIVERY`: exactly one of `delivery_address` OR `delivery_address_id` MUST be provided, else HTTP `422` (and `ValueError`/`ValidationError` at schema level). For `type=PICKUP` both stay optional.
  - When `delivery_address_id` is passed and belongs to the caller: checkout MUST load the row, snapshot it into `orders.delivery_address_snapshot` (JSONB, INV-014 immutable), and NOT call any geocoder stub.
  - When `delivery_address_id` belongs to a different user: checkout MUST reject with `404` (ownership leak prevention).
  - Haversine re-check: `validate_delivery_address` MUST be invoked with the loaded lat/lon EVERY checkout (shop settings can change between save and checkout).
- All tests expected to FAIL in RED — the target module `shared.models.delivery_address`, the router `core_api.routers.delivery_addresses`, the schema field `delivery_address_id`, the service changes in `checkout.py`, and migration `0006_delivery_addresses.py` do not yet exist.

## Capabilities

### New Capabilities
- `delivery-addresses`: Saved delivery addresses — DB model, Alembic migration, CRUD router under `/api/v1/profile/addresses`, checkout integration via `delivery_address_id`, ownership guard (404 on foreign), server-side Haversine validation at save-time, and immutable snapshot into `orders.delivery_address_snapshot` at checkout-time. Covers PDD §3 "Delivery Address", §5.2 `delivery_addresses` table, §7.3 step 3 (Haversine radius), INV-008 (server-side radius), INV-013 (PII isolation, CASCADE on user delete), INV-014 (order snapshot immutable).

### Modified Capabilities
- `order-checkout`: Extend `CreateOrderRequest` and the checkout pipeline to accept `delivery_address_id` as an alternative to the inline `delivery_address`. No change to pricing chain, no change to atomicity guarantees — only the source of the address snapshot changes (DB row vs request body).

## Impact

- Affected code (this RED cycle): `services/core-api/tests/` only — two new test files.
- Not touched in RED (delivered in `delivery-addresses-green`): `packages/shared/src/shared/models/delivery_address.py`, `packages/shared/src/shared/models/__init__.py`, `database/migrations/versions/0006_delivery_addresses.py`, `services/core-api/src/core_api/routers/delivery_addresses.py`, `services/core-api/src/core_api/services/delivery_addresses.py`, `services/core-api/src/core_api/schemas/delivery_address.py`, `services/core-api/src/core_api/schemas/order.py`, `services/core-api/src/core_api/services/checkout.py`, `services/core-api/src/core_api/main.py`, `services/core-api/src/core_api/rbac_matrix.py`.
- MVP Phase: Phase 4 — Delivery (PDD §7.1). Prepares for Yandex.Maps autocomplete (Phase 4 item 1) and courier workflow.
- External dependencies: none. Yandex.Maps geocoder stays a stub (owned by a separate Phase 4 feature); saved addresses already carry `lat`/`lon` so geocoding is skipped.

## Non-Goals

- No Yandex.Maps Suggest / Geocoder integration (owned by a separate Phase 4 feature).
- No frontend — no address-picker UI in `web/customer` (ships separately).
- No admin panel view of customer addresses (PII — admin sees only order snapshots per INV-013).
- No migration changes to `orders.delivery_address_snapshot` — the JSONB column already exists from `0005_phase3_schema.py` and stays as-is (INV-014 immutability preserved).
- No changes to Delivery Fee Chain (§7.4) or Time Slot Validation (§7.5).
- No courier assignment / delivery state machine — owned by Phase 4 dispatch feature.
- No account-deletion anonymization flow — CASCADE-on-delete is enough for this change; full anonymization sweep is a separate GDPR/152-FZ feature.
- No production code in RED — `delivery-addresses-green` ships all implementation.
