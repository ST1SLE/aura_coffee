# delivery-assignment-tests Specification

## Purpose
TBD - created by archiving change delivery-assignment-red. Update Purpose after archive.
## Requirements
### Requirement: RED pytest suite pins Delivery Assignment state machine (§6.3, INV-016)

The `services/core-api/tests/` directory SHALL contain a pytest suite that MUST fail against the current codebase because `shared.enums.DeliveryAssignmentStatus`, `shared.models.delivery_assignment.DeliveryAssignment`, `core_api.services.delivery_assignment`, `core_api.routers.courier`, and `core_api.services.order_lifecycle.transition_order_bridge` do not exist yet. The suite SHALL encode every allowed transition from PDD §6.3 as a happy-path test and every forbidden transition as a parametrised raise-test, per INV-016.

#### Scenario: module import probe fails until GREEN
- **WHEN** a test performs `from core_api.services.delivery_assignment import take_assignment, AssignmentTransitionError, AssignmentAlreadyTakenError`
- **THEN** the test MUST fail with `ModuleNotFoundError` on the current HEAD (no GREEN code landed)

#### Scenario: allow-list transition AWAITING_COURIER → COURIER_ASSIGNED asserts behaviour
- **WHEN** an in-memory `DeliveryAssignment(status=AWAITING_COURIER)` exists and the test calls `take_assignment(assignment_id, courier_id, db)`
- **THEN** the assertion SHALL read back `status == COURIER_ASSIGNED`, `courier_id == courier_id`, and `assigned_at is not None`

#### Scenario: allow-list transition COURIER_ASSIGNED → PICKED_UP via pickup_assignment
- **WHEN** an assignment with `status=COURIER_ASSIGNED` exists, the owning order has `status=READY`, and `pickup_assignment(aid, owner_cid, db)` is called
- **THEN** the assertion SHALL read back `assignment.status == PICKED_UP` and `picked_up_at is not None`

#### Scenario: allow-list transition PICKED_UP → DELIVERED via deliver_assignment
- **WHEN** assignment `status=PICKED_UP`, owning order `status=IN_DELIVERY`, and `deliver_assignment(aid, owner_cid, db)` is called
- **THEN** the assertion SHALL read back `assignment.status == DELIVERED` and `delivered_at is not None`

#### Scenario: allow-list transition AWAITING_COURIER → CANCELLED via cancel_assignment_for_order
- **WHEN** an assignment with `status=AWAITING_COURIER` exists and `cancel_assignment_for_order(order_id, db)` is called
- **THEN** the assertion SHALL read back `assignment.status == CANCELLED` and `cancelled_at is not None`

#### Scenario: allow-list transition COURIER_ASSIGNED → CANCELLED via cancel_assignment_for_order
- **WHEN** an assignment with `status=COURIER_ASSIGNED` exists and `cancel_assignment_for_order(order_id, db)` is called
- **THEN** the assertion SHALL read back `assignment.status == CANCELLED` and `cancelled_at is not None`

#### Scenario: every forbidden transition raises AssignmentTransitionError
- **WHEN** a parametrised test iterates every `(from, to)` pair from the Cartesian product of `DeliveryAssignmentStatus × DeliveryAssignmentStatus` minus the allow-list — including DELIVERED→*, CANCELLED→*, COURIER_ASSIGNED→AWAITING_COURIER, PICKED_UP→COURIER_ASSIGNED, PICKED_UP→CANCELLED, AWAITING_COURIER→PICKED_UP, AWAITING_COURIER→DELIVERED, COURIER_ASSIGNED→DELIVERED
- **THEN** each call to the corresponding service function SHALL raise `AssignmentTransitionError(reason="forbidden_transition")` and the assignment status MUST remain unchanged

#### Scenario: cancel_assignment_for_order on PICKED_UP is a no-op (PDD §6.3 forbids)
- **WHEN** an assignment with `status=PICKED_UP` exists and `cancel_assignment_for_order(order_id, db)` is called
- **THEN** the assertion SHALL read back `assignment.status == PICKED_UP` (unchanged) and the function returns `None`

### Requirement: Role gating and ownership checks pinned by RED tests (INV-010)

The RED suite SHALL pin INV-010 role isolation: courier-only endpoints reject non-courier roles with HTTP 403, and service-layer ownership checks (`pickup_assignment` / `deliver_assignment`) reject a different courier with `AssignmentTransitionError(reason="not_owner")`.

#### Scenario: courier endpoint rejects customer / barista / admin with 403
- **WHEN** a parametrised HTTP test calls any of `GET /api/v1/courier/assignments/available`, `GET /api/v1/courier/assignments/mine`, `POST /api/v1/courier/assignments/{id}/take`, `/pickup`, `/deliver` with `customer_headers`, `barista_headers`, or `admin_headers`
- **THEN** the response status code SHALL be 403

#### Scenario: pickup_assignment called by non-owner courier raises not_owner
- **WHEN** assignment `status=COURIER_ASSIGNED` with `courier_id=c1`, and `pickup_assignment(aid, c2, db)` is called with `c2 != c1`
- **THEN** the call SHALL raise `AssignmentTransitionError(reason="not_owner")` and no DB state mutates

#### Scenario: deliver_assignment called by non-owner courier raises not_owner
- **WHEN** assignment `status=PICKED_UP` with `courier_id=c1`, and `deliver_assignment(aid, c2, db)` is called
- **THEN** the call SHALL raise `AssignmentTransitionError(reason="not_owner")` and no DB state mutates

### Requirement: Bridge to Order Lifecycle §6.1 asserted in one DB transaction (INV-004)

The RED suite SHALL pin that `pickup_assignment` and `deliver_assignment` mutate BOTH the `delivery_assignment` row AND the linked `order` row in the same SQLAlchemy session, and that any mid-operation failure rolls back every mutation.

#### Scenario: pickup_assignment moves order READY → IN_DELIVERY atomically
- **WHEN** assignment `status=COURIER_ASSIGNED`, order `status=READY`, and `pickup_assignment(aid, cid, db)` completes successfully
- **THEN** `assignment.status == PICKED_UP` AND `order.status == IN_DELIVERY` — both visible in the same session after the call

#### Scenario: deliver_assignment moves order IN_DELIVERY → COMPLETED and accrues loyalty
- **WHEN** assignment `status=PICKED_UP`, order `status=IN_DELIVERY` with `total=100000`, `delivery_fee=15000`, shop `loyalty_percent=10`, and `deliver_assignment(aid, cid, db)` completes successfully
- **THEN** `assignment.status == DELIVERED`, `order.status == COMPLETED`, and exactly one `LoyaltyTransaction(type=ACCRUAL, amount=8500)` exists for the order's user (INV-003: 8500 = floor((100000 − 15000) × 10 / 100))

#### Scenario: pickup_assignment rejects when order not READY
- **WHEN** assignment `status=COURIER_ASSIGNED` but `order.status != READY` (e.g. PAID or PREPARING)
- **THEN** the call SHALL raise `AssignmentTransitionError(reason="order_not_ready")` and neither row mutates

#### Scenario: bridge rolls back on transition_order_bridge failure
- **WHEN** `pickup_assignment` is called, `transition_order_bridge` is monkey-patched to raise `RuntimeError`
- **THEN** the exception propagates AND after `db.rollback()` + `db.expire_all()` both `assignment.status` and `order.status` equal their pre-call values

### Requirement: PAID→PREPARING hook creates AWAITING_COURIER row for delivery orders (§6.1 ↔ §6.3)

The RED suite SHALL pin that `transition_order(order_id, PREPARING, "barista", db)` called on an order with `type=DELIVERY` inserts exactly one `DeliveryAssignment(status=AWAITING_COURIER, order_id=order.id)` in the same transaction, while the same transition on a `type=PICKUP` order creates no assignment.

#### Scenario: PAID → PREPARING on DELIVERY order inserts AWAITING_COURIER
- **WHEN** `order.type == DELIVERY`, `order.status == PAID`, and `transition_order(order.id, PREPARING, "barista", db)` completes
- **THEN** exactly one `DeliveryAssignment` exists with `order_id == order.id`, `status == AWAITING_COURIER`, `courier_id IS NULL`

#### Scenario: PAID → PREPARING on PICKUP order creates no assignment
- **WHEN** `order.type == PICKUP`, `order.status == PAID`, and `transition_order(order.id, PREPARING, "barista", db)` completes
- **THEN** no `DeliveryAssignment` row exists with `order_id == order.id`

### Requirement: Optimistic lock on take_assignment (PDD §6.3 «optimistic lock»)

The RED suite SHALL pin that two concurrent `take_assignment(aid, ...)` calls from different sessions result in exactly one `COURIER_ASSIGNED` write and one `AssignmentAlreadyTakenError`.

#### Scenario: two sessions race — only one wins
- **WHEN** session A calls `take_assignment(aid, c1, db_A)` and commits; session B then calls `take_assignment(aid, c2, db_B)` on the same `aid`
- **THEN** session B SHALL raise `AssignmentAlreadyTakenError` AND post-call the row has `courier_id == c1`, `status == COURIER_ASSIGNED`

#### Scenario: sqlite-in-memory skip guard
- **WHEN** `TEST_DATABASE_URL` is sqlite-in-memory (StaticPool, single connection)
- **THEN** the optimistic-lock test SHALL `pytest.skip(...)` because it requires two independent PostgreSQL connections

### Requirement: Courier router and RBAC matrix registration asserted by RED tests

The RED suite SHALL pin that `core_api.routers.courier.router` is registered by `core_api.main.app` and exposes the 5 paths listed below with `APIRouter(prefix="/api/v1/courier")`. It also pins that the RBAC matrix in `core_api.rbac_matrix.ROUTE_MATRIX` has exactly `{COURIER}` for each of these paths (test imports the matrix after GREEN lands).

#### Scenario: main.app has all 5 courier routes
- **WHEN** a test iterates `app.router.routes` after `from core_api.main import app`
- **THEN** the following (method, path_template) pairs MUST be present: `("GET", "/api/v1/courier/assignments/available")`, `("GET", "/api/v1/courier/assignments/mine")`, `("POST", "/api/v1/courier/assignments/{assignment_id}/take")`, `("POST", "/api/v1/courier/assignments/{assignment_id}/pickup")`, `("POST", "/api/v1/courier/assignments/{assignment_id}/deliver")`

#### Scenario: take endpoint forwards optimistic-lock race as 409
- **WHEN** the router is called with `courier_headers` and the service (monkey-patched at `core_api.routers.courier.take_assignment`) raises `AssignmentAlreadyTakenError`
- **THEN** the HTTP response SHALL be status 409 with a JSON body containing `reason == "already_taken"`

#### Scenario: pickup endpoint forwards not_owner as 403
- **WHEN** monkey-patched `pickup_assignment` raises `AssignmentTransitionError(reason="not_owner")`
- **THEN** the HTTP response SHALL be status 403 with `reason == "not_owner"` in the body

#### Scenario: deliver endpoint forwards forbidden_transition as 409
- **WHEN** monkey-patched `deliver_assignment` raises `AssignmentTransitionError(reason="forbidden_transition")`
- **THEN** the HTTP response SHALL be status 409 with `reason == "forbidden_transition"` in the body

#### Scenario: available endpoint returns AWAITING_COURIER list as JSON
- **WHEN** two seeded orders exist (one DELIVERY with assignment `AWAITING_COURIER`, one PICKUP with no assignment), and `GET /api/v1/courier/assignments/available` is called with `courier_headers`
- **THEN** the response is 200, a JSON list of length 1, containing the delivery assignment's id, linked order total, requested_time, and delivery_address_snapshot fields

