## Affected Modules

`[core-api]` (tests only in RED)

Implied for GREEN: `[core-api]`, `[shared]`, `[database]`.

## Context

PDD §3 and §5.2 define `delivery_addresses` as a first-class PII table. Today `orders.delivery_address_snapshot` is the only place an address lives — it is a JSONB snapshot written at checkout from the inline `CreateOrderRequest.delivery_address` body and is immutable per INV-014. To support returning customers in Phase 4 (PDD §7.1), the platform needs a persisted per-user address book with a default pointer, CRUD endpoints under the existing `/api/v1/profile` router, and a new `delivery_address_id` hop through checkout.

The `order-checkout-green` feature already landed:
- `CreateOrderRequest` (`services/core-api/src/core_api/schemas/order.py`) with an inline `DeliveryAddress` object on `delivery_address`.
- `core_api.services.checkout.create_order` running a validator chain and writing `delivery_address_snapshot=request.delivery_address.model_dump()`.
- `validate_delivery_address(lat, lon, shop_settings)` Haversine helper at `core_api.services.validators.delivery`.
- RBAC matrix in `core_api.rbac_matrix` (existing `POST /api/v1/orders` + `GET /api/v1/profile` entries give us the pattern).

The task is to extend all three without breaking any existing checkout contract. The `delivery_address_snapshot` JSONB shape stays identical (INV-014 — do NOT alter past orders), but its source at create-time can now be a DB row.

The RED cycle of this change ships ONLY failing tests. GREEN lands implementation.

## Goals / Non-Goals

**Goals:**
- Pin the CRUD contract for `/api/v1/profile/addresses` as executable tests: list (200), create (201 with Haversine radius enforcement, 422 out-of-radius), update (200 with atomic `is_default` flip, 404 on foreign row), delete (204, 404 on foreign row), auth guards (401 / 403).
- Pin the extended `CreateOrderRequest` contract: optional `delivery_address_id: UUID | None`, XOR with `delivery_address` for `type=DELIVERY`, 422 on both-set or neither-set.
- Pin checkout integration: ownership check on `delivery_address_id`, immutable snapshot into `delivery_address_snapshot`, Haversine re-check ALWAYS, geocoder never called for saved addresses.
- RBAC matrix coverage: the four new routes MUST appear in `ROUTE_MATRIX` with exactly `{CUSTOMER}` and MUST NOT appear in `PUBLIC_ROUTES`.
- All tests fail in RED with `ImportError`, `ModuleNotFoundError`, `KeyError`, or `AssertionError`. No test SHALL pass by accident.

**Non-Goals:**
- No Alembic migration assertions that re-read the schema — migration `0006_delivery_addresses.py` is tested by SQLAlchemy model round-trips in GREEN's `test_migration_0006_delivery_addresses.py`, NOT by this RED set. Reason: migration tests need a real PG connection; RED's suite runs on SQLite in the default CI path.
- No production code in RED.
- No tests for `delivery_address_snapshot` backward-compat with the inline path — that already has coverage in `test_checkout_service.py`; this RED set only adds the NEW paths (`delivery_address_id` load + ownership + Haversine re-check).
- No frontend tests.

## Decisions

### D1. Test file split — one file per public surface

Two files, no sharing:
- `tests/test_delivery_addresses_api.py` — HTTP tests for the CRUD router. Mirrors `test_profile_endpoints.py` and `test_route_cart.py` patterns (`TestClient`, `_patch_jwt`, `_auth_header`, `_make_token`).
- `tests/test_checkout_delivery_address_id.py` — schema-level + service-level tests for the checkout extension. Mirrors `test_checkout_service.py` patterns (in-body imports, `MagicMock`, `db_session` + `cart_redis` fixtures).

**Alternative considered:** one combined file. **Rejected:** the router and checkout extension are orthogonal surfaces; separate files let the GREEN author run just one suite at a time, and collection failures in one file don't mask the other.

### D2. Patch targets for validators in checkout tests

Follows `order-checkout-red` D1 (proven pattern). Tests patch by stringly-typed paths at the call site:
- `core_api.services.checkout.validate_delivery_address` — for Haversine re-check assertions.
- `core_api.services.checkout.get_shop_settings` — SHOULD exist if not already; tests patch the name, GREEN is free to implement it as a DB lookup or a dependency.

**Decision:** pin the symbol name `validate_delivery_address` as the patch target in `checkout.py` (same as existing `test_checkout_service.py`). Pin `load_saved_address(address_id, user_id, db)` as the new helper name — patched in some tests to return a fake `DeliveryAddress`-shaped object with `lat`, `lon`, `address_text`, `apartment`, etc.

### D3. Ownership leak prevention — 404 everywhere

For ALL endpoints that take `{address_id}` (PATCH, DELETE) AND for checkout with a foreign `delivery_address_id`, the response MUST be `404 Not Found`, NOT `403 Forbidden`. Reason: `403` on a real UUID confirms to the caller that the row exists (enumeration attack). `404` on both missing-and-foreign cases merges the two error spaces. PDD §2 (INV-010 role isolation) + §8.4 (PII minimisation) both argue for this.

**Alternative considered:** `403` on foreign, `404` on missing. **Rejected:** leaks row existence.

### D4. `is_default` atomicity

The partial unique index `(user_id) WHERE is_default = true` enforces at most one default per user. In `PATCH` when `is_default=true` is set, GREEN MUST wrap "demote previous default" + "promote new default" in a single DB transaction. RED asserts the observable outcome: after the PATCH, exactly one row for the user has `is_default=true` and it is the patched row.

**Alternative considered:** application-level check without partial index. **Rejected:** race-prone; the partial index is the authoritative guard. GREEN MUST ship both the index AND the explicit demote-in-same-txn logic.

### D5. Haversine re-check at checkout — ALWAYS

Even if an address passed the radius check at save time, `ShopSettings.delivery_radius_km` can be changed by admins. RED tests pin: `validate_delivery_address(lat, lon, shop_settings)` is called with the SAVED row's lat/lon (NOT from the request body) on EVERY checkout that uses a `delivery_address_id`, and an out-of-radius saved row fails the checkout with the existing `DeliveryRadiusError`/HTTP 409 mapping.

Rationale: INV-008 pins "server-side radius validation"; snapshotting alone is insufficient if the geometry changes under us.

### D6. Geocoder never called for saved addresses

Saved rows already carry `lat` + `lon` (validated at save time). RED pins: when `delivery_address_id` is provided, the geocoder stub MUST NOT be called. (The geocoder itself is a Phase 4 Yandex.Maps feature — today it's a no-op; the assertion is a forward-contract so GREEN doesn't wire it redundantly.)

Patch target: `core_api.services.checkout.geocode_address` (currently non-existent — test patches by string, fails in RED with `AttributeError`/`ModuleNotFoundError`; GREEN adds the symbol as a no-op stub for the unknown-coords branch).

**Alternative considered:** skip the assertion since no geocoder exists yet. **Rejected:** pinning the negative now prevents a GREEN implementor from calling it "just to be safe" and defeats the whole point of saved addresses.

### D7. XOR rule for `type=DELIVERY`

`CreateOrderRequest` with `type=DELIVERY` MUST have exactly one of `{delivery_address, delivery_address_id}` set — enforced at the Pydantic schema level with a `model_validator`, NOT in the service. FastAPI turns schema validation errors into `422`. For `type=PICKUP`, both fields SHOULD be `None`; if either is set, RED does NOT assert — GREEN MAY choose to reject or ignore. **Decision:** RED pins silent ignore for PICKUP (same as today's behaviour with `delivery_address`). Revisit in a follow-up if product asks.

### D8. Test fixtures — reuse existing

- `db_session` + `cart_redis` from `conftest.py` — no changes needed.
- `_checkout_user` — replicate the helper from `test_checkout_service.py` (inserts User + UserProfile + LoyaltyAccount). SHOULD eventually be promoted to a shared fixture — RED does NOT promote; GREEN's REFACTOR task may.
- Saved-address fixture `_saved_address(user_id, db, **overrides)` inserts a row into `delivery_addresses` and yields the model. Fails in RED with `ImportError` (model does not exist yet).

### D9. RED test module scaffolding

Each test file imports target symbols INSIDE each test body (never at module top level). Reason: collection-time `ImportError` would fail ALL tests with a single error; we want each test to fail independently with a meaningful message.

## Risks / Trade-offs

- [Risk] RED tests might spuriously pass if the partial unique index is absent AND two defaults slip through without ever being observed by the test. → Mitigation: `test_patch_is_default_demotes_previous` MUST seed TWO pre-existing addresses (one default) and observe the count after the PATCH, not just the single row's flag.
- [Risk] Patching a symbol that GREEN chooses NOT to import into `checkout.py` leaves the test silently green. → Mitigation: every patch target is ALSO asserted on (`mock.called`, `mock.call_args`). A patched-but-never-imported symbol cannot be `called`.
- [Risk] Haversine re-check path not hit when the service layer caches a shop_settings object. → Mitigation: RED patches `validate_delivery_address` as a MagicMock and asserts `.call_count >= 1` on every delivery-checkout invocation.
- [Risk] Ownership leak via timing: a 404 for missing and 404 for foreign take different code paths → different latencies. Out of scope for RED — document as a follow-up.

## 152-FZ Compliance

Per INV-013: `delivery_addresses` is PII. This RED cycle pins the contract that enables GREEN to:
- Store PII rows keyed by `user_id` (UUID, opaque).
- Use `ON DELETE CASCADE` so account deletion wipes all saved addresses (RED does not test CASCADE — that belongs to the migration test in GREEN).
- Keep `orders.delivery_address_snapshot` as the authoritative, immutable record for audit; deleting a saved address MUST NOT retroactively alter any past order (INV-014). RED asserts this implicitly: the snapshot path in checkout is a `model_dump()` of the loaded row, not a FK.

## Migration Plan

- Forward: `database/migrations/versions/0006_delivery_addresses.py` — `CREATE TABLE delivery_addresses` + partial unique index + `ix_delivery_addresses_user_id`. Schema-only (no data seeding). Down revision `0005`.
- Rollback: `DROP TABLE delivery_addresses` + `DROP INDEX` (both in `downgrade()`).
- Data backfill: none — no existing data needs to migrate. Customers accumulate addresses naturally from checkout-time save flow (Phase 4 follow-up).

(The migration itself is not tested in RED — it ships in GREEN alongside `test_migration_0006_delivery_addresses.py`.)

## Open Questions

None known. Symbol names and HTTP codes are pinned by the test set; GREEN has no remaining ambiguity.
