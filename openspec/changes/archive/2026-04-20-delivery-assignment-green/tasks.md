## 1. Shared package — enum + model

- [x] 1.1 [shared] GREEN: add `DeliveryAssignmentStatus(str, enum.Enum)` to `packages/shared/src/shared/enums.py` with values AWAITING_COURIER/COURIER_ASSIGNED/PICKED_UP/DELIVERED/CANCELLED → satisfies state-machine test 1.16 collection.
- [x] 1.2 [shared] GREEN: create `packages/shared/src/shared/models/delivery_assignment.py` defining `DeliveryAssignment` ORM (UUID pk, FK→orders UNIQUE, FK→staff_accounts nullable, status enum, timestamps `assigned_at`/`picked_up_at`/`delivered_at`/`cancelled_at`/`created_at`/`updated_at`) → satisfies imports in 4 RED test files.
- [x] 1.3 [shared] GREEN: register `DeliveryAssignment` in `packages/shared/src/shared/models/__init__.py` (import + `__all__`) → so `from shared.models import DeliveryAssignment` works inside test seeders.

## 2. Database — Alembic migration

- [x] 2.1 [database] MIGRATE: create `database/alembic/versions/0007_delivery_assignments.py` with `down_revision="0005_phase3_schema"` (or current head) — `upgrade()` creates native enum `delivery_assignment_status` + table `delivery_assignments` (matching model 1.2) + partial index `(status) WHERE status='awaiting_courier'`. `downgrade()` reverses in correct order.
- [x] 2.2 [database] VERIFY: run `alembic upgrade head` against test DB, confirm table+enum exist; then `alembic downgrade -1` cleanly drops them — confirms RED test 2.1 import + sqlite-conftest model registration both pass.

## 3. Order Lifecycle — refactor + bridge + hook

- [x] 3.1 [core-api] REFACTOR: in `services/core-api/src/core_api/services/order_lifecycle.py`, extract a private `_apply_transition(order_id, new_status, actor_role, db) -> Order` containing all current logic of `transition_order` EXCEPT `send_order_notification` and `db.commit()`. `transition_order` becomes: `order = _apply_transition(...); send_order_notification(order, new_status); db.commit(); return order`.
- [x] 3.2 [core-api] GREEN: add public `transition_order_bridge(order_id, new_status, actor_role, db) -> Order` that delegates to `_apply_transition` and returns the order with NO commit and NO notify → satisfies RED test 2.1 (`test_transition_order_bridge_exists`).
- [x] 3.3 [core-api] GREEN: inside `_apply_transition`, after the `(PAID, PREPARING)` transition is applied, INSERT `DeliveryAssignment(order_id=order.id, status=AWAITING_COURIER)` IFF `order.type == OrderType.DELIVERY`; flush. Satisfies RED tests 2.2 and 2.3.
- [x] 3.4 [core-api] VERIFY: run existing `pytest services/core-api/tests/test_order_lifecycle.py -v` — ALL existing order-lifecycle tests must still pass after refactor (sanity guard for D1).

## 4. Delivery Assignment service

- [x] 4.1 [core-api] GREEN: create `services/core-api/src/core_api/services/delivery_assignment.py` with `AssignmentTransitionError(Exception)` (with `reason: str`) and `AssignmentAlreadyTakenError(AssignmentTransitionError)` (`reason="already_taken"`). Satisfies imports in RED tests 1.1 and 4.1.
- [x] 4.2 [core-api] GREEN: implement `take_assignment(aid, courier_id, db)` using SQLAlchemy `update(...).where(id, status=AWAITING).values(...).returning(...)` — 0 rows → `assignment_not_found` (if missing) or `AssignmentAlreadyTakenError` (if exists). 1 row → `db.commit()` + return. Satisfies RED tests 1.2, 1.9, 1.15, 4.2.
- [x] 4.3 [core-api] GREEN: implement `pickup_assignment(aid, cid, db)` per design D4 (assignment_not_found → forbidden_transition → not_owner → order_not_ready → mutate → flush → bridge to IN_DELIVERY → commit). Satisfies RED tests 1.3, 1.10, 1.12, 1.14.
- [x] 4.4 [core-api] GREEN: implement `deliver_assignment(aid, cid, db)` per design D4 (analogous flow: status→DELIVERED, bridge to COMPLETED). Satisfies RED tests 1.4, 1.11, 1.13.
- [x] 4.5 [core-api] GREEN: implement `cancel_assignment_for_order(order_id, db)` per design D5 — AWAITING/COURIER_ASSIGNED → CANCELLED + cancelled_at; PICKED_UP/DELIVERED/CANCELLED/missing → return None. NO commit (caller responsibility). Satisfies RED tests 1.5, 1.6, 1.7, 1.8.
- [x] 4.6 [core-api] GREEN: implement `list_available_for_courier(db) -> list[...]` returning JOIN of `DeliveryAssignment` (status=AWAITING_COURIER) + `Order` (id, order_id, total, requested_time, delivery_address_snapshot). Each row exposes `id`, `order_id`, `total` as accessible attributes (Row/dataclass/dict — RED test 1.16 accepts both). Satisfies RED test 1.16.

## 5. Bridge integration tests (real bridge, not mocks)

- [x] 5.1 [core-api] VERIFY: run `pytest services/core-api/tests/test_delivery_assignment_bridge.py -v` — RED tests 2.4, 2.5 (real bridge), 2.6, 2.7 (rollback) must pass with implementation from §3 and §4.

## 6. order_cancel chain — call cancel_assignment_for_order

- [x] 6.1 [core-api] GREEN: in `services/core-api/src/core_api/services/order_cancel.py`, import `cancel_assignment_for_order` and call it AFTER `order.status = CANCELLED; db_session.flush()` and BEFORE `send_order_notification(...)` — satisfies RED test 2.8.
- [x] 6.2 [core-api] VERIFY: run `pytest services/core-api/tests/test_order_cancel.py -v` — existing cancel-chain tests must remain green (sanity guard for D10).

## 7. Courier router

- [x] 7.1 [core-api] GREEN: create `services/core-api/src/core_api/routers/courier.py` with `router = APIRouter(prefix="/api/v1/courier", tags=["courier"])` and module-level imports of `take_assignment`, `pickup_assignment`, `deliver_assignment`, `list_available_for_courier`, `AssignmentTransitionError`, `AssignmentAlreadyTakenError` (so tests can `patch.object(router_mod, ...)`). Satisfies RED test 3.1.
- [x] 7.2 [core-api] GREEN: add `GET /assignments/available` endpoint calling `list_available_for_courier(db)` and returning the list as JSON. Satisfies RED test 3.13.
- [x] 7.3 [core-api] GREEN: add `GET /assignments/mine` endpoint that filters by `courier_id == current_user["user_id"]` AND `status IN (COURIER_ASSIGNED, PICKED_UP)`. Satisfies route registration test 3.2.
- [x] 7.4 [core-api] GREEN: add `POST /assignments/{assignment_id}/take` endpoint with try/except mapping `AssignmentAlreadyTakenError`→409, `AssignmentTransitionError(reason="assignment_not_found")`→404, others→409. Satisfies RED tests 3.9, 3.12.
- [x] 7.5 [core-api] GREEN: add `POST /assignments/{assignment_id}/pickup` endpoint with same error mapping plus `not_owner`→403. Satisfies RED test 3.10.
- [x] 7.6 [core-api] GREEN: add `POST /assignments/{assignment_id}/deliver` endpoint with same error mapping. Satisfies RED test 3.11.
- [x] 7.7 [core-api] GREEN: register `courier_router` in `core_api/main.py` via `app.include_router(courier_router)`. Satisfies RED test 3.2.

## 8. RBAC matrix

- [x] 8.1 [core-api] GREEN: in `services/core-api/src/core_api/rbac_matrix.py`, add 5 entries — `("GET", "/api/v1/courier/assignments/available")`, `("GET", "/api/v1/courier/assignments/mine")`, `("POST", "/api/v1/courier/assignments/{assignment_id}/take")`, `("POST", "/api/v1/courier/assignments/{assignment_id}/pickup")`, `("POST", "/api/v1/courier/assignments/{assignment_id}/deliver")` — each mapped to `{COURIER}`. Satisfies RED tests 3.3, 3.4, 3.5, 3.6, 3.7, 3.8.

## 9. Final verification — all RED tests turn green

- [x] 9.1 [core-api] VERIFY: run `pytest services/core-api/tests/test_delivery_assignment_state_machine.py services/core-api/tests/test_delivery_assignment_bridge.py services/core-api/tests/test_courier_endpoints.py services/core-api/tests/test_delivery_assignment_optimistic_lock.py -v` — all 60 tests pass (4.2 may skip on sqlite-in-memory; PG connection turns it green).
- [x] 9.2 [core-api] VERIFY: run full `pytest services/core-api/tests/ -q` — confirm no regressions in `test_order_lifecycle.py`, `test_order_cancel.py`, or any other previously-green test.
