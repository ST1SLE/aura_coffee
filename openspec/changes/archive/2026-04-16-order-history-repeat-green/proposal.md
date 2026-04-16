## Why

The RED change `2026-04-16-order-history-repeat-red` locked 31 failing tests for the PDD §7.7 order history and repeat-order flows. This GREEN change is the minimal implementation that turns them green: a history service, a repeat-order service, DTOs, a router, and wiring into `main.py` + `rbac_matrix.py`.

MVP phase: **Phase 3 — Order & Payment** (PDD §7.1).

## What Changes

- Add Pydantic v2 response DTOs in `core_api.schemas.order_history`: `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `RepeatOrderSkippedEntry`, `RepeatOrderResult`.
- Add service `core_api.services.order_history.list_orders(user_id, page, per_page, db_session) -> OrderListResponse` — user-scoped paginated listing with `selectinload(Order.items)` (one extra SQL, not N+1).
- Add service `core_api.services.order_repeat.repeat_order(order_id, user_id, redis, db_session) -> RepeatOrderResult` implementing the PDD §7.7 Repeat Order Chain: ownership check → per-item availability resolution (stop-list / archived / deleted / size unavailable → entire item skip; modifier unavailable → modifier-only drop) → current-price re-cart via `CartService.add_item`. Raises `OrderNotFoundError` (404 mapping) and `NoItemsAvailableError` (422 mapping).
- Add router `core_api.routers.order_history` with `GET /api/v1/orders` (paginated history) and `POST /api/v1/orders/{order_id}/repeat`. Register in `core_api.main`. Authorize under CUSTOMER in `rbac_matrix.py`.
- Adjust the RED test `test_single_order_detail_is_not_duplicated` to an XFAIL in THIS worktree, with a note that the single-order-detail route is owned by the order-checkout feature and will land at merge time. (See Non-Goals + design.md D5.)

## Capabilities

### New Capabilities
<!-- None — specs are delta on the two capabilities already introduced by RED. -->

### Modified Capabilities
- `order-history`: replace the RED scenarios that assert "module/route is absent" with scenarios that assert the GREEN contract (symbols exist, `/api/v1/orders` returns paginated data under customer auth).
- `order-repeat`: replace the RED scenarios that assert "module/route is absent" with GREEN scenarios (symbols exist, the router returns `RepeatOrderResult`, cart is populated, no auto-checkout).

## Non-Goals

- Frontend UI for history and repeat (separate change in `web/customer`).
- Owning `GET /api/v1/orders/{order_id}` single-order-detail route — that belongs to the order-checkout feature. The RED expectation is relaxed via XFAIL in THIS worktree; at merge time the order-checkout route satisfies the test for downstream branches.
- Cancelling orders, tracking delivery, or any other PDD §7 flow.
- New migrations or changes to `orders` / `order_items` schema — all data shapes come from phase3-schema.
- Bulk-repeat or admin "re-dispatch" flows (analytics only).
- Caching. The service reads Postgres on every call; cache is out of scope for MVP.

## Impact

- **Code:** new `services/core-api/src/core_api/schemas/order_history.py`, `services/core-api/src/core_api/services/order_history.py`, `services/core-api/src/core_api/services/order_repeat.py`, `services/core-api/src/core_api/routers/order_history.py`; edits to `services/core-api/src/core_api/main.py` (include new router), `services/core-api/src/core_api/rbac_matrix.py` (two new routes → CUSTOMER).
- **Tests:** the RED files remain authoritative. One targeted edit to `tests/test_route_order_history.py` to XFAIL `test_single_order_detail_is_not_duplicated` (documented).
- **APIs:** two new HTTP endpoints — `GET /api/v1/orders`, `POST /api/v1/orders/{order_id}/repeat`.
- **Dependencies:** none added. Uses `CartService.add_item` (reads current prices server-side, INV-006/INV-014 enforced centrally).
- **Inviolable rules:** INV-002 (auth), INV-006 (stop-list — enforced via CartService), INV-013 (PII isolation preserved — reads by opaque UUID), INV-014 (order items remain immutable — the service only reads them).
- **Systems:** Postgres (read-only joined load on `orders`/`order_items`), Redis (writes via CartService). No migrations, no schema change.
