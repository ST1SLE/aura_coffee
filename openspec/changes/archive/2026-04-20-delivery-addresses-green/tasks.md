## 1. Model (shared package)

- [x] 1.1 [shared] MODEL: create `packages/shared/src/shared/models/delivery_address.py` defining `class DeliveryAddress(Base)` with `__tablename__ = "delivery_addresses"`. Columns: `id` (`UUID(as_uuid=True)` PK, `server_default=text("gen_random_uuid()")` — match whatever `0005` uses), `user_id` (`UUID(as_uuid=True)`, `ForeignKey("users.id", ondelete="CASCADE")`, non-null; INV-013), `label` (`String`, non-null), `address_text` (`String`, non-null), `lat` (`Float`, non-null), `lon` (`Float`, non-null), `apartment`, `entrance`, `floor`, `comment` (`String`, nullable), `is_default` (`Boolean`, non-null, default `False`), `created_at` / `updated_at` (`DateTime(timezone=True)`, server defaults `now()`). Relationship back to `User` (optional — only if needed elsewhere; tests don't require it).
- [x] 1.2 [shared] MODEL: add `__table_args__` with two indexes: `Index("ix_delivery_addresses_user_id", "user_id")` (non-unique, for list queries) AND `Index("ix_delivery_addresses_user_default", "user_id", unique=True, postgresql_where=text("is_default = true"))` — the RED test introspects `idx.dialect_options['postgresql']['where']`.
- [x] 1.3 [shared] MODEL: re-export in `packages/shared/src/shared/models/__init__.py` — `from shared.models.delivery_address import DeliveryAddress` + add `"DeliveryAddress"` to `__all__` if the module uses one. RED test `test_delivery_address_model_importable` imports via `from shared.models import DeliveryAddress`.

## 2. Alembic migration (additive)

- [x] 2.1 [database] MIGRATE: create `database/migrations/versions/0006_delivery_addresses.py` with `revision = "0006"`, `down_revision = "0005"`. `upgrade()` creates table `delivery_addresses` with the columns from 1.1, FK to `users.id` `ON DELETE CASCADE`, and both indexes from 1.2 (partial unique on `(user_id) WHERE is_default = true`, non-unique on `(user_id)`). `downgrade()` drops the table.
- [x] 2.2 [database] MIGRATE: run migration in the running stack (`docker compose exec core-api alembic upgrade head`) and confirm the table + indexes exist (`\d+ delivery_addresses`).

## 3. Pydantic schemas (core-api)

- [x] 3.1 [core-api] SCHEMA: create `services/core-api/src/core_api/schemas/delivery_address.py` with three models — `DeliveryAddressCreate` (required: `label`, `address_text`, `lat`, `lon`; optional: `apartment`, `entrance`, `floor`, `comment`, `is_default: bool = False`), `DeliveryAddressUpdate` (all fields optional; lat/lon omitted per D-non-goals), `DeliveryAddressRead` (all columns + `id`, `created_at`, `updated_at`). `model_config = {"from_attributes": True}` on `DeliveryAddressRead`.
- [x] 3.2 [core-api] SCHEMA: extend `services/core-api/src/core_api/schemas/order.py` — add `delivery_address_id: UUID | None = None` to `CreateOrderRequest`. Keep `delivery_address: DeliveryAddress | None = None` unchanged.
- [x] 3.3 [core-api] SCHEMA: add a `@model_validator(mode="after")` on `CreateOrderRequest` that enforces XOR when `type == OrderType.DELIVERY` (`has_inline == has_id` → `raise ValueError`). Pickup orders pass through (no assertion).

## 4. Domain service (core-api)

- [x] 4.1 [core-api] SERVICE: create `services/core-api/src/core_api/services/delivery_addresses.py`. Define a local `class DeliveryAddressNotFound(Exception)` (or reuse an existing domain-error base). All service functions take `db: Session` and `user_id: UUID` as first args.
- [x] 4.2 [core-api] SERVICE: implement `list_for_user(db, user_id) -> list[DeliveryAddress]` — `SELECT ... WHERE user_id = :uid ORDER BY is_default DESC, created_at ASC`.
- [x] 4.3 [core-api] SERVICE: implement `create_for_user(db, user_id, payload: DeliveryAddressCreate, shop_settings: ShopSettings) -> DeliveryAddress` — calls `validate_delivery_address(payload.lat, payload.lon, shop_settings)` (raises `DeliveryRadiusError` → 422 per RED spec, via router exception handler), inserts the row, `db.flush()` to get `id` + timestamps, returns the model. If `payload.is_default=True`, demote any existing default for the user in the same transaction (D4 pattern).
- [x] 4.4 [core-api] SERVICE: implement `update_for_user(db, user_id, address_id, payload: DeliveryAddressUpdate) -> DeliveryAddress` — `SELECT ... WHERE id=:id AND user_id=:uid` (raises `DeliveryAddressNotFound` on miss). If `payload.is_default == True`, in a single transaction: `UPDATE delivery_addresses SET is_default=false WHERE user_id=:uid AND is_default=true AND id != :id`, then apply the patch. Apply partial updates via `setattr` for non-None fields (support setting nullable fields to `None` explicitly via `model_dump(exclude_unset=True)`).
- [x] 4.5 [core-api] SERVICE: implement `delete_for_user(db, user_id, address_id) -> None` — `SELECT` for ownership check, then `db.delete(row)`. Raises `DeliveryAddressNotFound` on miss/foreign. Does NOT touch `orders.delivery_address_snapshot` (INV-014 — snapshots are detached).

## 5. Router (core-api)

- [x] 5.1 [core-api] ROUTER: create `services/core-api/src/core_api/routers/delivery_addresses.py`. `router = APIRouter()`. Dependencies: current-user JWT dependency (same one `profile.py` uses), `db = Depends(get_db)`, `shop_settings = Depends(get_shop_settings)` (or inline `db.get(ShopSettings, 1)`) for the POST path.
- [x] 5.2 [core-api] ROUTER: `GET "/"` → `response_model=list[DeliveryAddressRead]`, returns `list_for_user`.
- [x] 5.3 [core-api] ROUTER: `POST "/"` → `status_code=201`, `response_model=DeliveryAddressRead`, wraps `create_for_user` and converts `DeliveryRadiusError` to `HTTPException(422, detail="out of delivery radius")` (or reuses an existing handler if the project already maps this globally).
- [x] 5.4 [core-api] ROUTER: `PATCH "/{address_id}"` → `response_model=DeliveryAddressRead`, wraps `update_for_user`; catches `DeliveryAddressNotFound` → `HTTPException(404)`.
- [x] 5.5 [core-api] ROUTER: `DELETE "/{address_id}"` → `status_code=204`, `response_class=Response`, returns empty body; catches `DeliveryAddressNotFound` → `HTTPException(404)`.

## 6. Router registration + RBAC

- [x] 6.1 [core-api] WIRING: in `services/core-api/src/core_api/main.py` include the router — `from core_api.routers import delivery_addresses as delivery_addresses_router` and `app.include_router(delivery_addresses_router.router, prefix="/api/v1/profile/addresses", tags=["delivery-addresses"])`. Order the include near the existing `profile_router` include.
- [x] 6.2 [core-api] RBAC: extend `services/core-api/src/core_api/rbac_matrix.py::ROUTE_MATRIX` with four new entries — `("GET", "/api/v1/profile/addresses"): {Role.CUSTOMER}`, `("POST", "/api/v1/profile/addresses"): {Role.CUSTOMER}`, `("PATCH", "/api/v1/profile/addresses/{address_id}"): {Role.CUSTOMER}`, `("DELETE", "/api/v1/profile/addresses/{address_id}"): {Role.CUSTOMER}`. Do NOT touch `PUBLIC_ROUTES`.

## 7. Checkout extension (core-api)

- [x] 7.1 [core-api] CHECKOUT: in `services/core-api/src/core_api/services/checkout.py` expose `geocode_address` as a module-level name (import from wherever the current stub lives; if none exists yet, define a local stub `def geocode_address(address_text: str) -> tuple[float, float]: raise NotImplementedError`). RED patches `core_api.services.checkout.geocode_address` — the import target must resolve.
- [x] 7.2 [core-api] CHECKOUT: implement module-level `def load_saved_address(address_id: UUID, user_id: UUID, db: Session) -> DeliveryAddress` — `SELECT ... WHERE id=:id AND user_id=:uid`; on empty result raise a `DeliveryAddressNotFound` (reuse the one from `services.delivery_addresses`). RED tests patch this symbol by full path.
- [x] 7.3 [core-api] CHECKOUT: in `create_order`, when `req.type == OrderType.DELIVERY`, branch on `req.delivery_address_id`:
    - `if req.delivery_address_id is not None:` → `addr = load_saved_address(req.delivery_address_id, user_id, db)`; `validate_delivery_address(addr.lat, addr.lon, shop_settings)`; `snapshot = _build_snapshot_from_saved(addr)`. Do NOT call `geocode_address` on this path.
    - `else:` (inline path) → keep existing flow: `validate_delivery_address(req.delivery_address.lat, req.delivery_address.lon, shop_settings)`; `snapshot = req.delivery_address.model_dump(exclude_none=True)`.
- [x] 7.4 [core-api] CHECKOUT: add `def _build_snapshot_from_saved(addr: DeliveryAddress) -> dict`: returns `{"text": addr.address_text, "lat": addr.lat, "lon": addr.lon, **{k: v for k, v in [("apartment", addr.apartment), ("entrance", addr.entrance), ("floor", addr.floor), ("comment", addr.comment)] if v is not None}}` (INV-014 shape).
- [x] 7.5 [core-api] CHECKOUT: map `DeliveryAddressNotFound` to `HTTPException(404)` — either in the orders router or via a FastAPI exception handler; RED HTTP-level tests `test_checkout_foreign_address_id_returns_404` and `test_checkout_unknown_address_id_returns_404` expect `404` from `POST /api/v1/orders`.

## 8. VERIFY (GREEN)

- [x] 8.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_delivery_addresses_api.py services/core-api/tests/test_checkout_delivery_address_id.py -v`. Every test added by RED SHALL pass. The 11 documented pre-passing tests SHALL stay green. → 52/52 passed.
- [x] 8.2 [core-api] VERIFY: run the full `docker compose exec core-api pytest services/core-api/tests/` and confirm no regression — the 636 pre-existing pass-count (minus the 19 pre-existing failures unrelated to this change) SHALL hold. → 688 passed (636 baseline + 52 new), 19 failed (matches baseline), zero regressions.
- [x] 8.3 [core-api] VERIFY: `openspec validate delivery-addresses-green --strict` SHALL succeed before archive.
