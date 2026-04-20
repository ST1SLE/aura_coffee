## Context

RED archive `2026-04-20-delivery-addresses-red` left 41 failing tests across `services/core-api/tests/test_delivery_addresses_api.py` and `services/core-api/tests/test_checkout_delivery_address_id.py`, plus 11 "documented passes" (RBAC default-deny gates, regression guards). GREEN must flip those 41 to green and keep all 11 green as real guards — without breaking the 636 pre-existing tests.

Affected modules: `[core-api]` (routers, schemas, services, main, rbac_matrix), `[shared]` (one new model + one import re-export), `[database]` (one Alembic migration).

Existing conventions we piggy-back on:

- Profile routers already live under `/api/v1/profile/*`; `profile.py` shows the customer-only JWT-auth pattern and dependency wiring.
- `ShopSettings` is a singleton row (`id=1`) that already stores `shop_lat`, `shop_lon`, `delivery_radius_km`. `core_api.services.validators.delivery.validate_delivery_address(lat, lon, shop_settings)` is the canonical Haversine check; it raises `DeliveryRadiusError` → HTTP `409`.
- `rbac_matrix.ROUTE_MATRIX: dict[tuple[str, str], set[str]]` — mount-time assertion middleware requires each route to appear; `PUBLIC_ROUTES` is an opt-out for unauthenticated endpoints.
- `orders.delivery_address_snapshot` is a `JSONB` column (added in migration 0005). `create_order` already writes it on the inline path.
- `core_api.services.checkout.create_order` is synchronous SQLAlchemy 2.0 with a single `db.commit()` per order (INV-004 atomicity).

## Goals / Non-Goals

**Goals:**

- Make every RED test pass by adding the minimum surface area described in the proposal.
- Preserve INV-013 (FK `ON DELETE CASCADE`) and INV-014 (snapshot is a detached JSONB blob, no FK, byte-identical after source-row delete).
- Preserve INV-008: `validate_delivery_address` is called on every `type=DELIVERY` checkout — inline and saved paths.
- Keep the inline-delivery flow untouched in behavior (pure additive extension). `test_checkout_calls_validate_delivery_address_on_inline_path` must stay green.
- Use PostgreSQL-native constructs (JSONB, `uuid_generate_v4()`/`gen_random_uuid()` — whichever prior migrations use, partial unique index) because the RED tests skip on SQLite for Postgres-specific assertions.
- Keep the GREEN diff surgical: no refactors, no new dependencies, no cleanup of unrelated code.

**Non-Goals:**

- No frontend (web-customer profile screen, admin view) — belongs to a later `[web-customer]` change.
- No Yandex.Maps suggest/geocode — the `geocode_address` name is exposed purely so the RED "never called" assertion has a real patch target; its implementation stays the existing stub.
- No re-geocoding via PATCH — RED spec explicitly excludes `lat`/`lon` updates.
- No broader §8.4 account-deletion PII sweep — CASCADE-on-user-delete is the only INV-013 obligation in this change.
- No REFACTOR pass — sticking to the TDD "minimum code to pass" contract. Extract-shared-fixture type cleanup, if warranted, is a separate future change.
- No changes to existing migrations. 0006 is additive only.

## Decisions

### D1 — Where `DeliveryAddress` lives

Place the SQLAlchemy model in `packages/shared/src/shared/models/delivery_address.py` and re-export from `packages/shared/src/shared/models/__init__.py`, matching `UserProfile`, `ShopSettings`, etc. The tests import `from shared.models import DeliveryAddress`; any other placement would break RED contracts already archived.

Columns (match `test_delivery_address_model_importable`):

- `id: UUID` PK (server default matching prior migrations — we will use whatever `0005` does; most likely `gen_random_uuid()`),
- `user_id: UUID` FK `users.id` `ON DELETE CASCADE` (INV-013),
- `label: str` not-null,
- `address_text: str` not-null,
- `lat: float` not-null,
- `lon: float` not-null,
- `apartment, entrance, floor, comment: str | None`,
- `is_default: bool` default `False`,
- `created_at, updated_at: timezone-aware datetime`, server defaults `now()`.

Add two indexes in `__table_args__`: a partial unique index `(user_id) WHERE is_default = true` (argument `postgresql_where=...`; the RED test introspects `idx.dialect_options['postgresql']['where']`), and a plain non-unique index on `(user_id)`.

### D2 — Migration 0006 is additive-only

`database/migrations/versions/0006_delivery_addresses.py` creates only the new table + 2 indexes. Revision follows from `0005_phase3_schema`. No DROPs, no data migrations. Downgrade simply drops the table.

### D3 — Ownership mismatch = 404, not 403

Follows PDD §8.4 (minimize ownership leaks) and RED spec (`Scenario: Foreign address_id is rejected as 404`). Implement by always issuing a filtered SELECT `WHERE id = :id AND user_id = :user_id` and raising a `NotFoundError` (or `HTTPException(404)`) on empty result — no separate "exists? owned?" branch that could leak via timing.

Service returns a domain error class (e.g., `DeliveryAddressNotFound`) caught by the router and mapped to `HTTPException(404)`. The checkout service reuses the same helper and maps to `404` the same way.

### D4 — Atomic `is_default` flip

`update_for_user` runs inside the existing request-scoped `db` session. When the PATCH body sets `is_default=True`, perform a single transaction:

```sql
UPDATE delivery_addresses SET is_default = false
  WHERE user_id = :uid AND is_default = true AND id != :target_id;

UPDATE delivery_addresses SET is_default = true, ... WHERE id = :target_id AND user_id = :uid;
```

Then `db.flush()` (or let FastAPI's dependency auto-commit). The partial unique index provides a DB-level safety net: if two concurrent PATCHes race, one will hit the unique violation and roll back — the service does NOT need application-level locking. RED test `test_patch_is_default_true_demotes_previous_default` asserts both the post-state and the single-default invariant via a `SELECT COUNT`.

### D5 — Haversine re-check fires EVERY delivery checkout

`create_order` must call `validate_delivery_address(lat, lon, shop_settings)` on both the inline and saved paths. For the saved path, the args come from the loaded DB row — never from the request body, never cached. RED test `test_checkout_haversine_uses_saved_row_coords_not_request_body` pins this by patching the validator and inspecting call args.

Implementation shape:

```python
if req.type == OrderType.DELIVERY:
    if req.delivery_address_id is not None:
        addr = load_saved_address(req.delivery_address_id, user_id, db)  # raises NotFound
        validate_delivery_address(addr.lat, addr.lon, shop_settings)     # raises DeliveryRadiusError
        snapshot = _build_snapshot(addr)
    else:  # inline path, untouched
        validate_delivery_address(req.delivery_address.lat, req.delivery_address.lon, shop_settings)
        snapshot = req.delivery_address.model_dump(exclude_none=True)
    order.delivery_address_snapshot = snapshot
```

### D6 — Geocoder is NOT called when `delivery_address_id` is used

RED test `test_checkout_does_not_call_geocoder_when_address_id_provided` patches `core_api.services.checkout.geocode_address` and asserts `.called is False`. The saved row already carries validated `lat`/`lon`, so skipping geocode is correct AND cheap.

To give the `patch` a real symbol to replace, `geocode_address` must exist as a module-level name in `core_api.services.checkout`. If the current checkout code already exposes it (e.g., imported from a stub module), fine — just keep it. If not, import it (even if currently unused by the inline path) so RED's patch target resolves. The inline path may or may not call it; we will preserve current behavior.

### D7 — XOR validator on `CreateOrderRequest`

Pydantic v2 `model_validator(mode="after")` is the idiomatic spot. Raises `ValueError` (Pydantic wraps into `ValidationError` → FastAPI `422`). `type=PICKUP` is tolerant: either field set is silently ignored (no assertion, per RED spec).

```python
@model_validator(mode="after")
def _check_delivery_address_xor(self) -> Self:
    if self.type == OrderType.DELIVERY:
        has_inline = self.delivery_address is not None
        has_id = self.delivery_address_id is not None
        if has_inline == has_id:  # both or neither
            raise ValueError("for type=delivery, set exactly one of delivery_address / delivery_address_id")
    return self
```

### D8 — Snapshot shape is a flat JSON dict

RED spec: `{text, lat, lon}` mandatory; `apartment`, `entrance`, `floor`, `comment` optional (present only when non-null on the saved row). We will strip `None` before writing so the JSONB column stays tight. Inline path keeps its existing `exclude_none=True` semantics so the "shape matches" test compares equal dicts. If inline currently stores an unstripped shape, align it — but this is a narrow adjustment, not a refactor.

### D9 — RBAC wiring

`rbac_matrix.ROUTE_MATRIX` entries:

```python
("GET",    "/api/v1/profile/addresses"):             {Role.CUSTOMER},
("POST",   "/api/v1/profile/addresses"):             {Role.CUSTOMER},
("PATCH",  "/api/v1/profile/addresses/{address_id}"): {Role.CUSTOMER},
("DELETE", "/api/v1/profile/addresses/{address_id}"): {Role.CUSTOMER},
```

The matrix uses FastAPI path templates (`{address_id}`), not regex. RED tests access both `ROUTE_MATRIX` and `PUBLIC_ROUTES`; do not touch `PUBLIC_ROUTES`.

### D10 — Router registration

Mount in `core_api.main` next to the existing `profile_router`:

```python
from core_api.routers import delivery_addresses as delivery_addresses_router
app.include_router(delivery_addresses_router.router, prefix="/api/v1/profile/addresses", tags=["delivery-addresses"])
```

Do not re-prefix inside the router itself — keep the path-template key in `ROUTE_MATRIX` consistent with what FastAPI reports to `/openapi.json` (`paths["/api/v1/profile/addresses"]`, `paths["/api/v1/profile/addresses/{address_id}"]`).

### D11 — Schema `DeliveryAddressCreate.is_default` default

RED test `test_create_address_first_for_user_not_automatically_default` pins the contract: `is_default` is opt-in, even for the user's very first saved address. Therefore `DeliveryAddressCreate.is_default: bool = False` (no "auto-promote on first insert" logic). If the product later wants "first becomes default automatically", that's a separate change that must update both RED and spec.

## Risks / Trade-offs

- **`0006` migration vs SQLite conftest**: the test conftest seeds an in-memory SQLite with `Base.metadata.create_all(_sqlite_engine)` — so the new model registers automatically. Postgres tests run the migration. This matches the pattern used by `UserProfile` / `ShopSettings` and has no known issue, but we will re-run the full suite post-GREEN to catch any drift.
- **Partial unique index on SQLite**: SQLite does not support `postgresql_where`. The RED test that introspects it is `@pytest.mark.skipif(_IS_SQLITE, ...)`. We rely on that skip; GREEN does not attempt a portable fallback.
- **Concurrent default-flip race**: two `PATCH ... is_default=true` requests for the same user could both demote-then-promote. The partial unique index guarantees at most one survives. The second will 409/500 at commit. Accepted — the RED spec does not require transparent retry.
- **JSONB snapshot and Pydantic serialization**: `DeliveryAddress` columns include `created_at` / `updated_at` which we must NOT include in the snapshot (RED spec lists only `text`, `lat`, `lon`, `apartment`, `entrance`, `floor`, `comment`). The `_build_snapshot` helper will hand-select those fields — no `model_dump` of the whole model.
- **`geocode_address` module-level name**: if the current checkout module imports its stubs lazily, exposing `geocode_address` at module scope is a tiny API-surface change that still counts as "minimum code". Acceptable.
- **`CreateOrderRequest.extra` setting**: currently `extra="forbid"` (the RED failure proves it). Adding the field resolves that; the XOR validator adds the cross-field check. No config change needed.
- **11 RED tests currently PASSING**: 8 RBAC default-deny (pass because unmounted paths hit middleware 401/403), 1 `not_in_public_routes` (trivial), 1 `both_set_raises_validation_error` (passes via `extra=forbid` today — GREEN adds the field, so the existing pass silently becomes an XOR pass. Keep asserting `ValidationError` in the test), 1 inline-path validator-call guard (already green via existing checkout wiring). After GREEN, all 11 should remain green for real reasons. If any flip to red, the root cause is almost certainly our XOR or router wiring.
