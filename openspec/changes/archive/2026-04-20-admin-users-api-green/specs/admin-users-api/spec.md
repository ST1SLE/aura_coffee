## MODIFIED Requirements

_References: PDD §4.5 (Admin panel surfaces), §6.5 (User Account Lifecycle — ACTIVE↔BLOCKED, forbidden transitions), §7.1 Phase 6 item 2, §7.6 (Order Cancellation Chain), INV-004 (atomic financials), INV-010 (role isolation — admin-only endpoints), INV-013 (PII isolation — `phone_hash` is one-way, never exposed or searched; tombstone users excluded from detail)._

All requirements below have the same normative text as the archived RED change, with two modifications for every requirement:

**Previously:** each requirement contained a prose paragraph "In the RED change this symbol / route / rows MUST NOT exist" plus a leading `#### Scenario: RED — <symbol> is absent` that asserted `ImportError` / `KeyError` / route-count-zero.

**Now:** those RED-only paragraphs and RED-only scenarios are removed because the implementation has landed. Every other scenario is preserved verbatim and now describes positive, GREEN behavior. Also, RBAC scenarios of the form `GREEN contract — <route> maps to ADMIN only` are rephrased to drop the `GREEN contract — ` prefix (redundant now that the GREEN change is landed).

### Requirement: Admin-scoped user list service

The system SHALL expose a service function `list_users(db, *, status: str = "all", search: str | None = None, page: int = 1, per_page: int = 20) -> UserListResponse` at `core_api.services.admin_users`. It SHALL join `users` with `user_profiles` (LEFT JOIN — profile MAY be missing for `PENDING_VERIFICATION` accounts) and with `loyalty_accounts` (LEFT JOIN — balance coalesces to 0 when absent).

- `status` accepts one of `{"active", "blocked", "pending_verification", "deleted", "all"}`.
  - `"active"` → `users.status = ACTIVE AND users.deleted_at IS NULL`
  - `"blocked"` → `users.status = BLOCKED AND users.deleted_at IS NULL`
  - `"pending_verification"` → `users.status = PENDING_VERIFICATION AND users.deleted_at IS NULL`
  - `"deleted"` → `users.status = DELETED OR users.deleted_at IS NOT NULL`
  - `"all"` → no status filter; tombstones (`deleted_at IS NOT NULL`) ARE included.
- `search` is a case-insensitive prefix match over `user_profiles.display_name` (`LOWER(display_name) LIKE LOWER(?) || '%'`). `search` SHALL NOT be applied to `users.phone_hash` (INV-013). `search` SHALL NOT be applied to `phone` (encrypted).
- `page` SHALL be `>= 1`, `per_page` SHALL be in `[1, 100]`.
- Sort: `users.created_at DESC`.
- The returned `UserListResponse` SHALL contain `items: list[UserSummary]`, `total_count` (full filtered count, independent of page/per_page), `page`, `per_page`.
- `UserSummary` SHALL contain `id`, `status`, `display_name` (nullable), `loyalty_balance` (int, 0 when no loyalty_account row), `created_at`.
- `UserSummary` SHALL NOT contain `phone`, `phone_hash`, or any other PII fields beyond `display_name`.

#### Scenario: Default status=all includes every non-tombstone status and tombstones
- **GIVEN** seeded users across `{ACTIVE, BLOCKED, PENDING_VERIFICATION, DELETED}` plus one tombstone (`deleted_at IS NOT NULL`)
- **WHEN** the service is called with `status="all"`
- **THEN** every seeded user SHALL appear in the returned `items`

#### Scenario: status=active filters to ACTIVE users without tombstone
- **GIVEN** seeded users across all statuses plus a tombstoned ACTIVE user
- **WHEN** the service is called with `status="active"`
- **THEN** returned `items` SHALL contain only users with `status == ACTIVE AND deleted_at IS NULL`

#### Scenario: status=blocked filters to BLOCKED
- **GIVEN** seeded users across all statuses
- **WHEN** the service is called with `status="blocked"`
- **THEN** every returned `item.status` SHALL equal `"blocked"`

#### Scenario: status=pending_verification filters to PENDING_VERIFICATION
- **GIVEN** seeded users across all statuses
- **WHEN** the service is called with `status="pending_verification"`
- **THEN** every returned `item.status` SHALL equal `"pending_verification"`

#### Scenario: status=deleted returns DELETED and tombstoned rows
- **GIVEN** one `status=DELETED` user and one tombstoned ACTIVE user (`deleted_at IS NOT NULL`)
- **WHEN** the service is called with `status="deleted"`
- **THEN** both users SHALL appear in `items`

#### Scenario: search prefix-matches display_name case-insensitively
- **GIVEN** users with `display_name` values `["Alice", "alicia", "Bob"]`
- **WHEN** the service is called with `search="ali"` (lowercase)
- **THEN** the returned `items` SHALL contain exactly the two users with display_name starting with `"Ali"`/`"ali"` (prefix match), in `created_at DESC` order

#### Scenario: search does NOT match phone_hash fragments (INV-013)
- **GIVEN** a user whose `phone_hash` starts with hex digits `"abcdef"` and whose `display_name` is `"Valery"`
- **WHEN** the service is called with `search="abc"`
- **THEN** the returned `items` SHALL NOT include that user

#### Scenario: Pagination slices rows and reports full total_count
- **GIVEN** 25 seeded users
- **WHEN** the service is called with `status="all", page=2, per_page=10`
- **THEN** `total_count` SHALL equal 25 AND `items` SHALL contain exactly rows 11..20 in `created_at DESC` order

#### Scenario: Sort order is created_at DESC
- **GIVEN** three users with explicit `created_at` at T1 < T2 < T3
- **WHEN** the service is called with `status="all"`
- **THEN** the first three `items` SHALL be ordered `[T3, T2, T1]`

#### Scenario: loyalty_balance coalesces to 0 when loyalty_account missing
- **GIVEN** an ACTIVE user with no `loyalty_accounts` row
- **WHEN** the service is called with `status="active"`
- **THEN** the corresponding `item.loyalty_balance` SHALL equal `0`

### Requirement: Admin-scoped user detail service

The system SHALL expose a service function `get_user_detail(db, user_id: UUID) -> UserDetailResponse` at `core_api.services.admin_users`. It SHALL return the user's full admin-relevant profile, loyalty balance, last 20 loyalty transactions, and the count of active orders (orders NOT IN `{COMPLETED, CANCELLED}`). Tombstone users (`users.deleted_at IS NOT NULL`) SHALL raise a designated `UserNotFoundError` domain exception.

`UserDetailResponse` SHALL contain:
- `id: UUID`
- `status: str`
- `display_name: str | None`
- `language: str` (profile's `preferred_language`; `"ru"` when profile missing)
- `created_at: datetime`
- `loyalty_balance: int` (0 when account missing)
- `loyalty_transactions: list[LoyaltyTransactionItem]` — last 20 rows, `created_at DESC`
- `active_orders_count: int`

`LoyaltyTransactionItem` SHALL contain `id`, `type`, `amount`, `balance_after`, `description`, `created_at`. It SHALL NOT contain `user_id` or `order_id` (order-detail link is an admin-orders concern, not admin-users).

`UserDetailResponse` SHALL NOT contain `phone`, `phone_hash`, or `deleted_at`.

#### Scenario: Happy path returns merged shape
- **GIVEN** an ACTIVE user with display_name="Alice", preferred_language="en", loyalty balance=500, 5 loyalty transactions, 2 active orders and 3 completed orders
- **WHEN** the service is called with the user's id
- **THEN** the response SHALL report `status="active"`, `display_name="Alice"`, `language="en"`, `loyalty_balance=500`, `len(loyalty_transactions)==5`, and `active_orders_count==2`

#### Scenario: Loyalty transactions are the most recent 20, DESC
- **GIVEN** an ACTIVE user with 25 seeded loyalty transactions at monotonically increasing `created_at`
- **WHEN** the service is called with the user's id
- **THEN** `loyalty_transactions` SHALL contain exactly 20 items in `created_at DESC` order (rows 25..6)

#### Scenario: Tombstone user raises UserNotFoundError
- **GIVEN** a user with `deleted_at IS NOT NULL`
- **WHEN** the service is called with that user's id
- **THEN** the service SHALL raise `UserNotFoundError` (INV-013 — PII stripped, record not returnable to admin)

#### Scenario: Unknown user id raises UserNotFoundError
- **GIVEN** a fresh `uuid.uuid4()` not present in the users table
- **WHEN** the service is called with that id
- **THEN** the service SHALL raise `UserNotFoundError`

#### Scenario: active_orders_count ignores COMPLETED and CANCELLED
- **GIVEN** a user with orders in `{CREATED, PAID, PREPARING, READY, IN_DELIVERY, COMPLETED, CANCELLED}`
- **WHEN** the service is called with that user's id
- **THEN** `active_orders_count` SHALL equal 5 (all non-finalized)

### Requirement: Admin-scoped block user service

The system SHALL expose a service function `block_user(db, user_id: UUID) -> BlockUserResponse` at `core_api.services.admin_users` that transitions the user `ACTIVE → BLOCKED` per PDD §6.5 and cascades cancellation to admin-cancellable active orders via existing `core_api.services.order_cancel.cancel_order`.

The service SHALL:
1. `SELECT ... FOR UPDATE` on the `users` row;
2. if `user.status in {PENDING_VERIFICATION, DELETED}` or `user.deleted_at IS NOT NULL` → raise `InvalidUserStateError("invalid_user_state")`;
3. if `user.status == BLOCKED` → return `BlockUserResponse(user_id=user.id, status="blocked", cancelled_orders_count=0)` (idempotent no-op);
4. otherwise UPDATE `user.status = BLOCKED`, flush;
5. SELECT orders with `user_id == user.id AND status IN {CREATED, PAID, PREPARING, READY}` (explicitly EXCLUDING `IN_DELIVERY` per PDD §7.6 admin-cancel restriction);
6. for each order call `core_api.services.order_cancel.cancel_order(order_id=o.id, cancelled_by='admin', reason='user_blocked', db_session=db)`;
7. return `BlockUserResponse` with `cancelled_orders_count == len(cancelled_orders)`.

`BlockUserResponse` SHALL contain `user_id: UUID`, `status: Literal["blocked"]`, `cancelled_orders_count: int`.

#### Scenario: Happy path — ACTIVE user with active orders is blocked and cascades
- **GIVEN** an ACTIVE user with 3 orders in statuses `[CREATED, PAID, PREPARING]`
- **AND** `core_api.services.order_cancel.celery_app.send_task` is mocked
- **WHEN** the service is called with the user's id
- **THEN** `user.status` SHALL equal `BLOCKED` in the DB
- **AND** all 3 orders SHALL have `status == CANCELLED` in the DB
- **AND** the response SHALL be `BlockUserResponse(user_id=..., status="blocked", cancelled_orders_count=3)`

#### Scenario: COMPLETED and CANCELLED orders are untouched
- **GIVEN** an ACTIVE user with orders `[PAID, COMPLETED, CANCELLED]`
- **WHEN** the service is called
- **THEN** only the `PAID` order SHALL be newly cancelled
- **AND** `cancelled_orders_count` SHALL equal 1
- **AND** the `COMPLETED` and `CANCELLED` orders' `status` SHALL remain unchanged

#### Scenario: IN_DELIVERY orders are skipped silently
- **GIVEN** an ACTIVE user with orders `[PAID, IN_DELIVERY]`
- **WHEN** the service is called
- **THEN** the PAID order SHALL become CANCELLED
- **AND** the IN_DELIVERY order SHALL remain IN_DELIVERY
- **AND** `cancelled_orders_count` SHALL equal 1

#### Scenario: Idempotent — re-blocking BLOCKED user is a no-op
- **GIVEN** a user already at `status=BLOCKED` with no active orders
- **WHEN** the service is called
- **THEN** the response SHALL be `BlockUserResponse(user_id=..., status="blocked", cancelled_orders_count=0)`
- **AND** NO `cancel_order` invocation SHALL have occurred (celery mock uncalled)

#### Scenario: PENDING_VERIFICATION user raises invalid_user_state
- **GIVEN** a user at `status=PENDING_VERIFICATION`
- **WHEN** the service is called
- **THEN** the service SHALL raise `InvalidUserStateError("invalid_user_state")`

#### Scenario: DELETED user raises invalid_user_state
- **GIVEN** a user at `status=DELETED` OR with `deleted_at IS NOT NULL`
- **WHEN** the service is called
- **THEN** the service SHALL raise `InvalidUserStateError("invalid_user_state")`

### Requirement: Admin-scoped unblock user service

The system SHALL expose a service function `unblock_user(db, user_id: UUID) -> BlockUserResponse` at `core_api.services.admin_users` that transitions the user `BLOCKED → ACTIVE` per PDD §6.5.

The service SHALL:
1. `SELECT ... FOR UPDATE` on the `users` row;
2. if `user.status in {PENDING_VERIFICATION, DELETED}` or `user.deleted_at IS NOT NULL` → raise `InvalidUserStateError("invalid_user_state")`;
3. if `user.status == ACTIVE` → return `BlockUserResponse(user_id=user.id, status="active", cancelled_orders_count=0)` (idempotent no-op);
4. otherwise UPDATE `user.status = ACTIVE`, commit;
5. return `BlockUserResponse(user_id=user.id, status="active", cancelled_orders_count=0)`.

No cascade SHALL be performed — cancelled orders SHALL NOT be resurrected (INV-016 — CANCELLED is a terminal state in §6.1).

#### Scenario: Happy path — BLOCKED user is unblocked
- **GIVEN** a BLOCKED user
- **WHEN** the service is called
- **THEN** `user.status` SHALL equal `ACTIVE` in the DB
- **AND** the response SHALL be `BlockUserResponse(user_id=..., status="active", cancelled_orders_count=0)`

#### Scenario: Idempotent — unblocking ACTIVE user is a no-op
- **GIVEN** an ACTIVE user
- **WHEN** the service is called
- **THEN** `user.status` SHALL remain `ACTIVE`
- **AND** the response SHALL be `BlockUserResponse(user_id=..., status="active", cancelled_orders_count=0)`

#### Scenario: PENDING_VERIFICATION user raises invalid_user_state
- **GIVEN** a user at `status=PENDING_VERIFICATION`
- **WHEN** the service is called
- **THEN** the service SHALL raise `InvalidUserStateError("invalid_user_state")`

#### Scenario: DELETED user raises invalid_user_state
- **GIVEN** a user at `status=DELETED` OR with `deleted_at IS NOT NULL`
- **WHEN** the service is called
- **THEN** the service SHALL raise `InvalidUserStateError("invalid_user_state")`

#### Scenario: No cascade — previously cancelled orders stay cancelled
- **GIVEN** a BLOCKED user with 2 orders in `status=CANCELLED` (cancelled during block)
- **WHEN** the service is called
- **THEN** both orders SHALL remain at `status=CANCELLED`

### Requirement: Admin-scoped loyalty adjustment service

The system SHALL expose a service function `adjust_loyalty(db, user_id: UUID, delta: int, reason: str) -> LoyaltyAdjustResponse` at `core_api.services.admin_users` that credits or debits loyalty balance and records a `LoyaltyTransaction` of type `ADMIN_ADJUSTMENT`. All steps SHALL execute in a single DB transaction with `SELECT ... FOR UPDATE` on `loyalty_accounts` (INV-004).

The service SHALL:
1. validate `delta != 0`, `1 <= len(reason) <= 500` (validation MAY happen at Pydantic layer in the router);
2. `SELECT ... FOR UPDATE` on `users` — if `user.status in {PENDING_VERIFICATION, DELETED}` or `user.deleted_at IS NOT NULL` → raise `InvalidUserStateError("invalid_user_state")`;
3. `SELECT ... FOR UPDATE` on `loyalty_accounts.user_id = user_id`;
4. compute `new_balance = account.balance + delta`; if `new_balance < 0` → raise `InsufficientBalanceError("insufficient_balance")`;
5. UPDATE `account.balance = new_balance`;
6. INSERT `LoyaltyTransaction(user_id=user_id, order_id=NULL, type=LoyaltyTransactionType.ADMIN_ADJUSTMENT, amount=delta, balance_after=new_balance, description=reason)`;
7. `db.commit()`;
8. return `LoyaltyAdjustResponse(transaction_id=..., new_balance=..., delta=delta)`.

BLOCKED users SHALL be accepted — returning points before unblock is a legitimate operator workflow.

`LoyaltyAdjustResponse` SHALL contain `transaction_id: UUID`, `new_balance: int`, `delta: int`.

#### Scenario: Positive delta credits balance and creates ADMIN_ADJUSTMENT transaction
- **GIVEN** an ACTIVE user with loyalty balance=100
- **WHEN** the service is called with `delta=500, reason="customer service credit"`
- **THEN** the `loyalty_accounts.balance` SHALL equal `600`
- **AND** a new `LoyaltyTransaction` SHALL exist with `type=ADMIN_ADJUSTMENT, amount=500, balance_after=600, description="customer service credit", order_id IS NULL`
- **AND** the response SHALL be `LoyaltyAdjustResponse(transaction_id=<new tx id>, new_balance=600, delta=500)`

#### Scenario: Negative delta debits balance
- **GIVEN** an ACTIVE user with loyalty balance=500
- **WHEN** the service is called with `delta=-200, reason="chargeback adjustment"`
- **THEN** `loyalty_accounts.balance` SHALL equal `300`
- **AND** a `LoyaltyTransaction` SHALL exist with `amount=-200, balance_after=300`

#### Scenario: Insufficient balance raises error and rolls back
- **GIVEN** an ACTIVE user with loyalty balance=100
- **WHEN** the service is called with `delta=-200, reason="oops"`
- **THEN** the service SHALL raise `InsufficientBalanceError("insufficient_balance")`
- **AND** `loyalty_accounts.balance` SHALL remain `100`
- **AND** NO new `LoyaltyTransaction` SHALL have been inserted

#### Scenario: BLOCKED user is accepted
- **GIVEN** a BLOCKED user with loyalty balance=100
- **WHEN** the service is called with `delta=200, reason="refund before unblock"`
- **THEN** the service SHALL succeed with `new_balance=300`

#### Scenario: PENDING_VERIFICATION user raises invalid_user_state
- **GIVEN** a PENDING_VERIFICATION user (with loyalty_account balance=0)
- **WHEN** the service is called with `delta=100, reason="x"`
- **THEN** the service SHALL raise `InvalidUserStateError("invalid_user_state")`

#### Scenario: DELETED user raises invalid_user_state
- **GIVEN** a user at `status=DELETED` OR with `deleted_at IS NOT NULL`
- **WHEN** the service is called with any delta and reason
- **THEN** the service SHALL raise `InvalidUserStateError("invalid_user_state")`

### Requirement: GET /api/v1/admin/users list endpoint

The system SHALL expose `GET /api/v1/admin/users` at `core_api.routers.admin_users`. The route SHALL be open to `{ADMIN}` only via RBAC; `{BARISTA, COURIER, CUSTOMER}` SHALL receive 403, and requests without a valid Bearer token SHALL receive 401. Query parameters:

- `status: str = Query("all")` — validated against `{"active","blocked","pending_verification","deleted","all"}`; invalid values → 422.
- `search: str | None = Query(None, max_length=100)`.
- `page: int = Query(1, ge=1)`.
- `per_page: int = Query(20, ge=1, le=100)`.

Response body: `UserListResponse` from `core_api.schemas.admin_users`.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a GET matching `/api/v1/admin/users`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends `GET /api/v1/admin/users` without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for customer role
- **WHEN** a client sends `GET /api/v1/admin/users` with a customer JWT
- **THEN** the response status SHALL be 403

#### Scenario: 403 for barista role
- **WHEN** a client sends `GET /api/v1/admin/users` with a barista JWT
- **THEN** the response status SHALL be 403

#### Scenario: 403 for courier role
- **WHEN** a client sends `GET /api/v1/admin/users` with a courier JWT
- **THEN** the response status SHALL be 403

#### Scenario: 422 when per_page exceeds 100
- **WHEN** an admin sends `GET /api/v1/admin/users?per_page=101`
- **THEN** the response status SHALL be 422

#### Scenario: 422 when status is invalid
- **WHEN** an admin sends `GET /api/v1/admin/users?status=bogus`
- **THEN** the response status SHALL be 422

#### Scenario: Admin sees list with full total_count
- **GIVEN** 25 seeded users across statuses
- **WHEN** an admin sends `GET /api/v1/admin/users?page=1&per_page=10`
- **THEN** the response status SHALL be 200
- **AND** `body.total_count` SHALL equal 25
- **AND** `len(body.items)` SHALL equal 10

#### Scenario: Response body never exposes phone or phone_hash
- **GIVEN** at least one user with `phone_hash` set
- **WHEN** an admin sends `GET /api/v1/admin/users`
- **THEN** no item in the response JSON SHALL contain a `phone` or `phone_hash` key

### Requirement: GET /api/v1/admin/users/{user_id} detail endpoint

The system SHALL expose `GET /api/v1/admin/users/{user_id}` at `core_api.routers.admin_users`. RBAC: `{ADMIN}`; other roles → 403; no token → 401. Tombstone users (`users.deleted_at IS NOT NULL`) → 404. Unknown `user_id` → 404. Response body: `UserDetailResponse` from `core_api.schemas.admin_users`.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a GET matching `/api/v1/admin/users/{user_id}`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends `GET /api/v1/admin/users/<uuid>` without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for non-admin staff (barista)
- **WHEN** a barista sends `GET /api/v1/admin/users/<uuid>`
- **THEN** the response status SHALL be 403

#### Scenario: Admin reads user detail
- **GIVEN** an ACTIVE user with display_name="Alice", 500 loyalty balance, 2 active orders
- **WHEN** an admin sends `GET /api/v1/admin/users/{user.id}`
- **THEN** the response status SHALL be 200
- **AND** `body.display_name == "Alice"`
- **AND** `body.loyalty_balance == 500`
- **AND** `body.active_orders_count == 2`

#### Scenario: 404 on tombstone user
- **GIVEN** a user with `deleted_at IS NOT NULL`
- **WHEN** an admin sends `GET /api/v1/admin/users/{user.id}`
- **THEN** the response status SHALL be 404

#### Scenario: 404 on unknown user id
- **WHEN** an admin sends `GET /api/v1/admin/users/<random-uuid>`
- **THEN** the response status SHALL be 404

#### Scenario: Detail body never exposes phone or phone_hash
- **WHEN** an admin fetches user detail
- **THEN** the response JSON SHALL NOT contain `phone`, `phone_hash`, or `deleted_at` keys

### Requirement: POST /api/v1/admin/users/{user_id}/block endpoint

The system SHALL expose `POST /api/v1/admin/users/{user_id}/block` at `core_api.routers.admin_users`. RBAC: `{ADMIN}`; other roles → 403; no token → 401. 404 on unknown user id. 409 on forbidden PDD §6.5 state. Response: `BlockUserResponse`.

Delegates cascade to `core_api.services.order_cancel.cancel_order` (PDD §7.6). IN_DELIVERY orders SHALL be skipped silently.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a POST matching `/api/v1/admin/users/{user_id}/block`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends the POST without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for barista
- **WHEN** a barista sends the POST
- **THEN** the response status SHALL be 403

#### Scenario: Happy path — ACTIVE user with active orders
- **GIVEN** an ACTIVE user with 3 orders `[CREATED, PAID, PREPARING]`
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 200
- **AND** `body.status == "blocked"` AND `body.cancelled_orders_count == 3`

#### Scenario: Idempotent — BLOCKED user
- **GIVEN** a user already at BLOCKED
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 200
- **AND** `body.cancelled_orders_count == 0`

#### Scenario: 409 on PENDING_VERIFICATION
- **GIVEN** a PENDING_VERIFICATION user
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 409
- **AND** `body.detail == "invalid_user_state"`

#### Scenario: 409 on DELETED user
- **GIVEN** a user with `deleted_at IS NOT NULL`
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 409

#### Scenario: 404 on unknown user id
- **WHEN** an admin sends the POST for a random UUID
- **THEN** the response status SHALL be 404

### Requirement: POST /api/v1/admin/users/{user_id}/unblock endpoint

The system SHALL expose `POST /api/v1/admin/users/{user_id}/unblock` at `core_api.routers.admin_users`. RBAC: `{ADMIN}`; other roles → 403; no token → 401. 404 on unknown user id. 409 on forbidden state. Response: `BlockUserResponse`.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a POST matching `/api/v1/admin/users/{user_id}/unblock`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends the POST without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for customer
- **WHEN** a customer sends the POST
- **THEN** the response status SHALL be 403

#### Scenario: Happy path — BLOCKED user is unblocked
- **GIVEN** a BLOCKED user
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 200
- **AND** `body.status == "active"`

#### Scenario: Idempotent — ACTIVE user
- **GIVEN** an ACTIVE user
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 200 AND `body.status == "active"`

#### Scenario: 409 on PENDING_VERIFICATION
- **GIVEN** a PENDING_VERIFICATION user
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 409

#### Scenario: 409 on DELETED user
- **GIVEN** a user with `deleted_at IS NOT NULL`
- **WHEN** an admin sends the POST
- **THEN** the response status SHALL be 409

### Requirement: POST /api/v1/admin/users/{user_id}/loyalty/adjust endpoint

The system SHALL expose `POST /api/v1/admin/users/{user_id}/loyalty/adjust` at `core_api.routers.admin_users`. RBAC: `{ADMIN}`; other roles → 403; no token → 401. 404 on unknown user id. 409 on `{PENDING_VERIFICATION, DELETED}` status. 422 on body validation (`delta == 0`, `len(reason) not in [1, 500]`). 422 on `insufficient_balance`. Response: `LoyaltyAdjustResponse`.

Request body schema (`LoyaltyAdjustRequest`):
- `delta: int` — must be non-zero; Pydantic `Field(..., description="signed delta, cannot be zero")`.
- `reason: str` — `Field(..., min_length=1, max_length=500)`.

#### Scenario: Route is registered exactly once
- **WHEN** a test inspects `app.routes` for a POST matching `/api/v1/admin/users/{user_id}/loyalty/adjust`
- **THEN** the match count SHALL equal 1

#### Scenario: 401 without Authorization header
- **WHEN** a client sends the POST without an `Authorization` header
- **THEN** the response status SHALL be 401

#### Scenario: 403 for non-admin roles
- **WHEN** a barista / courier / customer sends the POST
- **THEN** the response status SHALL be 403

#### Scenario: Happy path — positive delta
- **GIVEN** an ACTIVE user with loyalty balance=100
- **WHEN** an admin sends `{ "delta": 500, "reason": "service credit" }`
- **THEN** the response status SHALL be 200
- **AND** `body.new_balance == 600`
- **AND** `body.delta == 500`
- **AND** `body.transaction_id` SHALL be a valid UUID string

#### Scenario: 422 on delta=0
- **WHEN** an admin sends `{ "delta": 0, "reason": "x" }`
- **THEN** the response status SHALL be 422

#### Scenario: 422 on empty reason
- **WHEN** an admin sends `{ "delta": 10, "reason": "" }`
- **THEN** the response status SHALL be 422

#### Scenario: 422 on reason length 501
- **WHEN** an admin sends `{ "delta": 10, "reason": <501 chars> }`
- **THEN** the response status SHALL be 422

#### Scenario: 422 on insufficient balance
- **GIVEN** an ACTIVE user with loyalty balance=100
- **WHEN** an admin sends `{ "delta": -200, "reason": "x" }`
- **THEN** the response status SHALL be 422
- **AND** `body.detail` SHALL mention `"insufficient_balance"`

#### Scenario: 409 on DELETED user
- **GIVEN** a user with `deleted_at IS NOT NULL`
- **WHEN** an admin sends any adjust body
- **THEN** the response status SHALL be 409

#### Scenario: BLOCKED user is accepted
- **GIVEN** a BLOCKED user with balance=100
- **WHEN** an admin sends `{ "delta": 200, "reason": "refund before unblock" }`
- **THEN** the response status SHALL be 200
- **AND** `body.new_balance == 300`

### Requirement: RBAC matrix registers the admin-users prefix

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain rows for each of the five new admin-users routes, all mapped to role set `{ADMIN}`. None SHALL appear in `PUBLIC_ROUTES`.

#### Scenario: admin-users list route maps to ADMIN only
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/admin/users")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: admin-users detail route maps to ADMIN only
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/admin/users/{user_id}")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: admin-users block route maps to ADMIN only
- **WHEN** a test reads `ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/block")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: admin-users unblock route maps to ADMIN only
- **WHEN** a test reads `ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/unblock")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: admin-users loyalty/adjust route maps to ADMIN only
- **WHEN** a test reads `ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust")]`
- **THEN** the value SHALL equal `{ADMIN}`

#### Scenario: admin-users routes are not public
- **WHEN** a test reads `PUBLIC_ROUTES`
- **THEN** none of the five admin-users route tuples SHALL be present

### Requirement: Customer-scoped profile endpoints remain unchanged

The existing `/api/v1/profile/*` routes and the customer-scoped profile / loyalty / address services SHALL remain unmodified. Admin SHALL reach user data strictly via the new `/api/v1/admin/users/*` prefix. No customer-scoped route SHALL be added to the admin RBAC matrix.

#### Scenario: Existing `GET /api/v1/profile` row still lists CUSTOMER only
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/profile")]`
- **THEN** the value SHALL equal `{CUSTOMER}`

#### Scenario: Existing `GET /api/v1/profile/loyalty` row still lists CUSTOMER only
- **WHEN** a test reads `ROUTE_MATRIX[("GET", "/api/v1/profile/loyalty")]`
- **THEN** the value SHALL equal `{CUSTOMER}`
