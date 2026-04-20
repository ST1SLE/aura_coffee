## 1. PREREQ — verify RED phase landed

- [x] 1.1 PREREQ: [core-api] Confirm `services/core-api/tests/test_admin_orders_list.py`, `test_admin_orders_detail.py`, `test_admin_orders_rbac.py` exist (committed by `admin-orders-api-red`). No edit.
- [x] 1.2 PREREQ: [core-api] Confirm `seed_orders_across_statuses` and `MixedStatusSeed` are present in `services/core-api/tests/_factories/orders.py`. No edit.
- [x] 1.3 PREREQ: [core-api] Confirm reuse targets exist: `core_api.schemas.order_history.OrderListResponse` and `OrderResponse` (with `user_id`); `core_api.rbac_matrix.{ADMIN, BARISTA, ROUTE_MATRIX, PUBLIC_ROUTES}`. Read-only.

## 2. GREEN — staff-scoped service helpers in `services/order_history.py`

- [x] 2.1 GREEN: [core-api] Edit `services/core-api/src/core_api/services/order_history.py` — add `class OrderNotFoundForStaffError(Exception): pass` near the existing domain errors. Satisfies RED tests `test_get_order_for_staff_raises_on_unknown_id` (3.3).
- [x] 2.2 GREEN: [core-api] Edit `services/core-api/src/core_api/services/order_history.py` — implement `get_order_for_staff(*, order_id: UUID, db_session: Session) -> OrderResponse`: SELECT order by id (no `user_id` predicate); if `None` raise `OrderNotFoundForStaffError`; map to `OrderResponse` with the same field-mapping helper used by `list_orders`. Satisfies RED tests 3.1, 3.2, 3.3, 5.4, 5.5.
- [x] 2.3 GREEN: [core-api] Edit `services/core-api/src/core_api/services/order_history.py` — implement `list_orders_for_staff(*, status_filter: OrderStatus | str, type_filter: OrderType | None, page: int, per_page: int, db_session: Session) -> OrderListResponse`. Branch on `status_filter == "active"` vs concrete `OrderStatus`; AND-combine `type_filter` when set; choose ORDER BY `updated_at DESC` for finalized statuses else `created_at DESC`; compute `total_count` then slice with `offset/limit`. Satisfies RED tests 2.1–2.8.

## 3. GREEN — RBAC matrix wiring

- [x] 3.1 GREEN: [core-api] Edit `services/core-api/src/core_api/rbac_matrix.py` — append two rows to `ROUTE_MATRIX`: `("GET", "/api/v1/admin/orders"): {ADMIN, BARISTA}` and `("GET", "/api/v1/admin/orders/{order_id}"): {ADMIN, BARISTA}`. Do NOT touch `PUBLIC_ROUTES`. Do NOT modify the existing `("GET", "/api/v1/orders/{order_id}")` row. Satisfies RED tests 6.1, 6.2, 6.3, 6.4 (untouched customer-list signature is preserved by 2.x), 6.5.

## 4. GREEN — admin orders router module

- [x] 4.1 GREEN: [core-api] Create `services/core-api/src/core_api/routers/admin_orders.py` — instantiate `router = APIRouter(prefix="/api/v1/admin", tags=["admin-orders"])`; define `list_admin_orders` handler accepting `status: str = "active"`, `type: OrderType | None = None`, `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=100)`, `db = Depends(get_db)`; coerce `status` → `"active"` or `OrderStatus(status)` (422 on invalid); call `list_orders_for_staff`; return `OrderListResponse`. Define `get_admin_order_detail(order_id: UUID, db = Depends(get_db))`; call `get_order_for_staff`, translate `OrderNotFoundForStaffError → HTTPException(404)`. Satisfies RED router tests 4.x and 5.x (handlers + 404 path).

## 5. GREEN — register router in app

- [x] 5.1 GREEN: [core-api] Edit `services/core-api/src/core_api/main.py` — `from core_api.routers.admin_orders import router as admin_orders_router` and `app.include_router(admin_orders_router)`. Place near other staff routers (after RBAC middleware wiring). Satisfies RED tests `test_admin_orders_list_route_not_registered` (4.1) and `test_admin_orders_detail_route_not_registered` (5.1).

## 6. VERIFY — entire suite green

- [x] 6.1 VERIFY: [core-api] Run `pytest services/core-api/tests/test_admin_orders_list.py services/core-api/tests/test_admin_orders_detail.py services/core-api/tests/test_admin_orders_rbac.py -x -q` from the worktree (or via the worktree docker stack if PG is up). All 33 tests SHALL pass.
- [x] 6.2 VERIFY: [core-api] Run the full `services/core-api/tests/` suite — confirm no regression in customer-scoped order routes (`test_route_order_history.py`, `test_route_orders.py`, RBAC suites).
- [x] 6.3 VERIFY: [core-api] `python3 -m py_compile services/core-api/src/core_api/services/order_history.py services/core-api/src/core_api/routers/admin_orders.py services/core-api/src/core_api/rbac_matrix.py services/core-api/src/core_api/main.py` returns SYNTAX_OK.
