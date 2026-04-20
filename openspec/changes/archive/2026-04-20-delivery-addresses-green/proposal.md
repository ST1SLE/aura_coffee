## Why

RED tests for saved delivery addresses are now in the tree (archive `2026-04-20-delivery-addresses-red`). GREEN implements the minimum production code needed to turn them from red to green — no behavior beyond the RED contract. This is the second half of the two-change TDD loop mandated by AGENTS.md §Two-Change Model.

Scope references PDD §3 "Delivery Address", §5.2 `delivery_addresses` + `orders.delivery_address_snapshot`, §7.3 "Address Validation Chain", and Inviolable Rules INV-002 (auth for mutations), INV-008 (server-side delivery-radius check), INV-013 (PII isolation + CASCADE on user delete), INV-014 (order snapshot immutability).

## What Changes

- Add `shared.models.delivery_address.DeliveryAddress` SQLAlchemy model (table `delivery_addresses`), re-exported from `shared.models` so tests and services can `from shared.models import DeliveryAddress`. Table carries FK `user_id → users.id ON DELETE CASCADE` (INV-013) and a partial unique index on `(user_id) WHERE is_default = true` (single-default invariant enforced at the DB layer).
- Add Alembic migration `0006_delivery_addresses.py` — creates ONLY the `delivery_addresses` table + both indexes (partial unique default, non-unique `(user_id)`). No other schema touches.
- Add `core_api.schemas.delivery_address` — request/response Pydantic v2 models (`DeliveryAddressCreate`, `DeliveryAddressUpdate`, `DeliveryAddressRead`) mirroring the column set.
- Add `core_api.services.delivery_addresses` — pure business-logic helpers: `list_for_user`, `create_for_user` (server-side Haversine via existing `validate_delivery_address`), `update_for_user` (atomic default-flip in a single transaction), `delete_for_user`. Ownership mismatch raises a domain error that maps to HTTP `404` (never `403` — leak-avoidance per PDD §8.4).
- Add `core_api.routers.delivery_addresses` — FastAPI `APIRouter` mounted under `/api/v1/profile/addresses` with four operations (`GET /`, `POST /`, `PATCH /{address_id}`, `DELETE /{address_id}`). Wire the router into `core_api.main.app` alongside existing profile routers.
- Extend `core_api.rbac_matrix.ROUTE_MATRIX` with four new entries, each mapping to `{CUSTOMER}`. Do NOT add any of the new routes to `PUBLIC_ROUTES`.
- Extend `core_api.schemas.order.CreateOrderRequest` with `delivery_address_id: UUID | None = None`. Add a `model_validator(mode="after")` that enforces XOR between `delivery_address` and `delivery_address_id` when `type == DELIVERY` (both-set or neither-set raises `ValidationError` → HTTP `422`). Pickup orders SHOULD NOT set either; if they do, ignore silently (no assertion).
- Extend `core_api.services.checkout.create_order` — when `delivery_address_id` is set, load the row via a new module-level `load_saved_address(address_id, user_id, db)` helper (raises a domain error that maps to `404` on miss/foreign). The loaded row's `lat`/`lon` feed directly into `validate_delivery_address` (called EVERY delivery checkout — INV-008, shop settings can drift between save-time and checkout-time). Snapshot the saved row into `orders.delivery_address_snapshot` JSONB as a plain dict `{text, lat, lon, apartment?, entrance?, floor?, comment?}` (INV-014 immutability — the snapshot must NOT alias or FK-reference the saved row).
- Expose `geocode_address` (and, where absent, `load_saved_address`) as module-level names on `core_api.services.checkout` so the RED mock-patches that assert non-invocation work against real import targets.

## Capabilities

### New Capabilities

- (none): `delivery-addresses` was introduced by the RED archive. GREEN only fulfils its existing requirements with production code — it does not add new capability slots.

### Modified Capabilities

- `delivery-addresses`: no requirement text changes. GREEN adds the production code that makes the six RED requirements ("DeliveryAddress model exists", "CRUD router authorized for Customer", "GET returns own only", "POST validates radius via Haversine", "PATCH atomic default flip", "DELETE 404 on foreign + past-snapshot immutable") actually pass.
- `order-checkout`: no requirement text changes. GREEN adds the production code that makes the five RED requirements ("CreateOrderRequest accepts optional delivery_address_id", "XOR between the two delivery fields", "Checkout loads saved address and enforces ownership", "Checkout snapshots saved address immutably", "Haversine radius re-check on every delivery checkout") actually pass.

## Impact

- **Affected code** (`[core-api]`, `[shared]`, `[database]`):
  - `packages/shared/src/shared/models/delivery_address.py` (new)
  - `packages/shared/src/shared/models/__init__.py` (re-export `DeliveryAddress`)
  - `database/migrations/versions/0006_delivery_addresses.py` (new — schema-only, table + 2 indexes)
  - `services/core-api/src/core_api/schemas/delivery_address.py` (new)
  - `services/core-api/src/core_api/schemas/order.py` (extend `CreateOrderRequest`: optional `delivery_address_id` + XOR `model_validator`)
  - `services/core-api/src/core_api/services/delivery_addresses.py` (new — CRUD + atomic default flip + ownership 404)
  - `services/core-api/src/core_api/services/checkout.py` (add `load_saved_address` + `geocode_address` module-level names; branch on `delivery_address_id`; snapshot into JSONB; Haversine re-check on saved path)
  - `services/core-api/src/core_api/routers/delivery_addresses.py` (new)
  - `services/core-api/src/core_api/main.py` (mount the new router)
  - `services/core-api/src/core_api/rbac_matrix.py` (four new entries → `{CUSTOMER}`)
- **APIs added**: `GET /api/v1/profile/addresses`, `POST /api/v1/profile/addresses`, `PATCH /api/v1/profile/addresses/{address_id}`, `DELETE /api/v1/profile/addresses/{address_id}`. All customer-only, JWT-authenticated via existing middleware.
- **APIs modified**: `POST /api/v1/orders` accepts optional `delivery_address_id` (XOR with inline `delivery_address`). `type=delivery` with both-set or neither-set now returns `422`. `delivery_address_id` pointing to a non-existent or foreign row returns `404`.
- **DB**: one new table `delivery_addresses` with a partial unique index on `(user_id) WHERE is_default=true` and a `(user_id)` list index; FK `user_id ON DELETE CASCADE` (INV-013). No other schema changes, no destructive operations on existing tables.
- **Dependencies**: no new Python packages. Reuses existing `validate_delivery_address`, `DeliveryRadiusError`, `ShopSettings`, and the existing `core_api.deps.database.get_db` + JWT auth dependencies.
- **Non-goals**: no Yandex.Maps suggest/geocode integration (stays stubbed per PDD §11.1 order-2), no frontend UI, no admin view of addresses, no account-deletion PII-anonymization sweep (INV-013's CASCADE-on-user-delete is covered; the broader §8.4 anonymization flow belongs to its own change), no re-geocoding via PATCH (lat/lon changes via PATCH are explicitly out of scope per the RED spec).
