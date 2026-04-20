# delivery-assignment Specification

## Purpose
TBD - created by archiving change delivery-assignment-green. Update Purpose after archive.
## Requirements
### Requirement: DeliveryAssignmentStatus enum exists in shared.enums (PDD §6.3)

The `shared.enums` module SHALL export `DeliveryAssignmentStatus` as a `str, enum.Enum` with exactly five values matching PDD §6.3: `AWAITING_COURIER="awaiting_courier"`, `COURIER_ASSIGNED="courier_assigned"`, `PICKED_UP="picked_up"`, `DELIVERED="delivered"`, `CANCELLED="cancelled"`.

#### Scenario: import succeeds and values are exhaustive
- **WHEN** a test does `from shared.enums import DeliveryAssignmentStatus` and reads the set of `.value` strings
- **THEN** the import succeeds and the value set equals `{"awaiting_courier", "courier_assigned", "picked_up", "delivered", "cancelled"}`

### Requirement: DeliveryAssignment ORM model exists in shared.models (PDD §6.3, §5)

The `shared.models.delivery_assignment` module SHALL define `DeliveryAssignment` as a SQLAlchemy 2.0 declarative model bound to `shared.models.Base`, registered in `shared.models.__init__` so `from shared.models import DeliveryAssignment` succeeds. Columns: UUID `id` (pk, default uuid4), UUID `order_id` (FK→orders.id, ondelete=RESTRICT, NOT NULL, UNIQUE), UUID `courier_id` (FK→staff_accounts.id, ondelete=RESTRICT, nullable), `status` (native enum `delivery_assignment_status`, NOT NULL, default `awaiting_courier`), nullable `assigned_at`/`picked_up_at`/`delivered_at`/`cancelled_at` (timestamptz), `created_at` and `updated_at` (timestamptz, server_default `now()`).

#### Scenario: model class is registered and importable
- **WHEN** a test does `from shared.models import DeliveryAssignment`
- **THEN** the class is importable, its `__tablename__` equals `"delivery_assignments"`, and `Base.metadata.tables` contains `"delivery_assignments"`

#### Scenario: order_id is UNIQUE (1:1 with orders)
- **WHEN** two `DeliveryAssignment(order_id=O)` rows for the same `O` are inserted on PostgreSQL
- **THEN** the second insert SHALL raise `sqlalchemy.exc.IntegrityError`

### Requirement: Alembic migration 0007 creates delivery_assignments + native enum + partial index

The repository SHALL contain `database/alembic/versions/0007_delivery_assignments.py` whose `upgrade()` creates: (1) PostgreSQL native enum `delivery_assignment_status` with the five §6.3 values, (2) table `delivery_assignments` matching the model, (3) partial index `(status) WHERE status='awaiting_courier'`. `downgrade()` SHALL drop the index, then the table, then the enum.

#### Scenario: alembic upgrade head creates the table and enum
- **WHEN** `alembic upgrade head` runs against an empty PostgreSQL database
- **THEN** the table `delivery_assignments` and the enum type `delivery_assignment_status` exist (visible via `pg_class` / `pg_type`)

### Requirement: take_assignment uses optimistic lock (PDD §6.3 «optimistic lock»)

`core_api.services.delivery_assignment.take_assignment(aid, courier_id, db)` SHALL execute a single `UPDATE delivery_assignments SET status='courier_assigned', courier_id=:cid, assigned_at=:now WHERE id=:aid AND status='awaiting_courier' RETURNING *` and treat zero rows affected as a race loss. If 0 rows AND the row does not exist → `AssignmentTransitionError(reason="assignment_not_found")`. If 0 rows AND the row exists → `AssignmentAlreadyTakenError` (subclass of `AssignmentTransitionError` with `reason="already_taken"`). If 1 row updated → return the updated `DeliveryAssignment` after `db.commit()`.

#### Scenario: happy path sets status, courier_id, and assigned_at
- **WHEN** an `AWAITING_COURIER` assignment exists and `take_assignment(aid, c1, db)` is called
- **THEN** post-call `assignment.status == COURIER_ASSIGNED`, `courier_id == c1`, and `assigned_at is not None`

#### Scenario: race loss raises AssignmentAlreadyTakenError
- **WHEN** session A calls `take_assignment(aid, c1, db_A)` and commits, then session B calls `take_assignment(aid, c2, db_B)`
- **THEN** session B raises `AssignmentAlreadyTakenError` and the row remains `(courier_id=c1, status=COURIER_ASSIGNED)`

### Requirement: pickup_assignment / deliver_assignment enforce ownership and order precondition (INV-010)

`pickup_assignment(aid, cid, db)` SHALL: read the assignment (404 if missing), require `assignment.status == COURIER_ASSIGNED` (else `forbidden_transition`), require `assignment.courier_id == cid` (else `not_owner`), require linked `order.status == READY` (else `order_not_ready`), set `assignment.status = PICKED_UP` + `picked_up_at = now()`, flush, then call `transition_order_bridge(order_id, IN_DELIVERY, "courier", db)`, then `db.commit()`. `deliver_assignment(aid, cid, db)` SHALL behave identically with `(PICKED_UP→DELIVERED, IN_DELIVERY→COMPLETED)`.

#### Scenario: pickup with non-owner courier raises not_owner and leaves DB unchanged
- **WHEN** assignment `(status=COURIER_ASSIGNED, courier_id=c1)` exists and `pickup_assignment(aid, c2, db)` is called with `c2 != c1`
- **THEN** the call raises `AssignmentTransitionError(reason="not_owner")` AND the assignment row's `status` stays `COURIER_ASSIGNED`

#### Scenario: pickup when order is not READY raises order_not_ready
- **WHEN** assignment `(status=COURIER_ASSIGNED)` and order `status` is not READY (e.g. PAID, PREPARING, IN_DELIVERY)
- **THEN** the call raises `AssignmentTransitionError(reason="order_not_ready")` AND no DB row mutates

#### Scenario: deliver happy path moves order to COMPLETED and accrues loyalty
- **WHEN** assignment `(status=PICKED_UP, courier_id=c1)`, order `(status=IN_DELIVERY, total=100000, delivery_fee=15000)`, shop `loyalty_percent=10`, and `deliver_assignment(aid, c1, db)` is called
- **THEN** assignment.status == DELIVERED, order.status == COMPLETED, exactly one `LoyaltyTransaction(type=ACCRUAL, amount=8500)` exists for the order — INV-003: `8500 = floor((100000 - 15000) * 10 / 100)`

### Requirement: cancel_assignment_for_order is no-op for PICKED_UP/DELIVERED (PDD §6.3)

`cancel_assignment_for_order(order_id, db)` SHALL set `status=CANCELLED, cancelled_at=now()` ONLY when the assignment exists AND its current status is in `{AWAITING_COURIER, COURIER_ASSIGNED}`. For `PICKED_UP`, `DELIVERED`, `CANCELLED`, OR if no assignment row exists for the order → return `None` and mutate nothing.

#### Scenario: PICKED_UP cancel is no-op
- **WHEN** assignment with `status=PICKED_UP` exists and `cancel_assignment_for_order(order_id, db)` is called
- **THEN** the call returns `None` and `assignment.status` remains `PICKED_UP`

#### Scenario: AWAITING_COURIER → CANCELLED
- **WHEN** assignment with `status=AWAITING_COURIER` exists and `cancel_assignment_for_order(order_id, db)` is called
- **THEN** the function returns the assignment, `assignment.status == CANCELLED`, and `cancelled_at is not None`

### Requirement: order_lifecycle splits into _apply_transition + transition_order + transition_order_bridge (PDD §6.1, INV-016)

`core_api.services.order_lifecycle` SHALL expose a NEW public function `transition_order_bridge(order_id, new_status, actor_role, db)` that runs the same allow-list / role / type-guard validation and the same `_accrue_loyalty` side effect as `transition_order`, BUT does NOT call `db.commit()` and does NOT call `send_order_notification`. The existing public `transition_order` SHALL retain its current behavior (commit + notify) so all existing `test_order_lifecycle.py` tests stay green.

#### Scenario: import probe
- **WHEN** a test does `from core_api.services.order_lifecycle import transition_order_bridge`
- **THEN** the import SHALL succeed

#### Scenario: bridge applies transition without committing
- **WHEN** `transition_order_bridge(order_id, READY, "barista", db)` is called on a PREPARING order
- **THEN** `order.status` becomes `READY` in the session, but `db.in_transaction()` remains `True` and `send_order_notification` is NOT called

### Requirement: PAID→PREPARING hook creates AWAITING_COURIER for DELIVERY orders only (§6.1 ↔ §6.3)

`_apply_transition` SHALL, on a successful `(PAID, PREPARING)` transition, INSERT exactly one `DeliveryAssignment(order_id=order.id, status=AWAITING_COURIER, courier_id=NULL)` IFF `order.type == DELIVERY`. For `order.type == PICKUP`, NO assignment row SHALL be created.

#### Scenario: DELIVERY order — one row created
- **WHEN** `transition_order(order_id, PREPARING, "barista", db)` is called on a DELIVERY+PAID order
- **THEN** exactly one `delivery_assignment` row exists with `order_id == order.id`, `status == AWAITING_COURIER`, `courier_id IS NULL`

#### Scenario: PICKUP order — no assignment created
- **WHEN** `transition_order(order_id, PREPARING, "barista", db)` is called on a PICKUP+PAID order
- **THEN** zero `delivery_assignment` rows exist with `order_id == order.id`

### Requirement: Courier router exposes 5 endpoints under /api/v1/courier (PDD §6.3)

`core_api.routers.courier` SHALL expose `APIRouter(prefix="/api/v1/courier", tags=["courier"])` with: `GET /assignments/available`, `GET /assignments/mine`, `POST /assignments/{assignment_id}/take`, `POST /assignments/{assignment_id}/pickup`, `POST /assignments/{assignment_id}/deliver`. `core_api.main.app.include_router(courier_router)` SHALL register it. Domain errors are mapped: `not_owner`→403, `forbidden_transition`/`order_not_ready`/`already_taken`→409, `assignment_not_found`→404. Each error response body SHALL be a JSON object containing `reason`.

#### Scenario: 5 routes registered under /api/v1/courier
- **WHEN** a test inspects `core_api.main.app.router.routes`
- **THEN** all 5 (method, path) pairs above are present

#### Scenario: AssignmentAlreadyTakenError → 409
- **WHEN** `core_api.routers.courier.take_assignment` raises `AssignmentAlreadyTakenError`
- **THEN** the HTTP response status is 409 and body contains `"reason": "already_taken"`

#### Scenario: AssignmentTransitionError(not_owner) → 403
- **WHEN** `core_api.routers.courier.pickup_assignment` raises `AssignmentTransitionError(reason="not_owner")`
- **THEN** the HTTP response status is 403 and body contains `"reason": "not_owner"`

#### Scenario: available endpoint returns top-level JSON list
- **WHEN** `list_available_for_courier` returns a list of length 1 and the courier calls `GET /api/v1/courier/assignments/available`
- **THEN** the HTTP response status is 200 and `response.json()` is a JSON list of length 1 (NOT wrapped in `{items: [...]}`)

### Requirement: RBAC matrix grants courier-only access to courier routes (INV-010)

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain entries for each of the 5 courier routes mapping to exactly `{COURIER}`. Customers, baristas, and admins calling these routes SHALL receive HTTP 403.

#### Scenario: ROUTE_MATRIX entries equal {COURIER}
- **WHEN** a test reads `ROUTE_MATRIX[(method, path)]` for each of the 5 courier routes
- **THEN** the value equals exactly the set `{COURIER}` (no admin, no barista, no customer)

#### Scenario: non-courier roles get 403
- **WHEN** a request with `customer_headers`, `barista_headers`, or `admin_headers` hits any of the 5 courier routes
- **THEN** the HTTP response status is 403

### Requirement: order_cancel.cancel_order calls cancel_assignment_for_order in same transaction (PDD §7.6 + §6.3)

`core_api.services.order_cancel.cancel_order` SHALL invoke `cancel_assignment_for_order(order_id, db_session)` AFTER setting `order.status = CANCELLED` and BEFORE `send_order_notification`, so admin-initiated cancellation of a DELIVERY order with an active assignment atomically cancels both rows in one DB transaction.

#### Scenario: admin cancels DELIVERY order — both rows become CANCELLED
- **WHEN** an order with `type=DELIVERY, status=PAID` is transitioned to PREPARING (creating AWAITING_COURIER), then `cancel_order(order_id, "admin", reason, db)` is called
- **THEN** post-call `order.status == CANCELLED` AND `assignment.status == CANCELLED`, both in the same session

