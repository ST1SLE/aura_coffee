## 1. PREREQ — verify RED phase landed

- [x] 1.1 PREREQ: [core-api] Confirm `services/core-api/tests/test_admin_users_list.py`, `test_admin_users_detail.py`, `test_admin_users_block.py`, `test_admin_users_unblock.py`, `test_admin_users_loyalty_adjust.py`, `test_admin_users_rbac.py` exist (committed by `admin-users-api-red`). No edit.
- [x] 1.2 PREREQ: [core-api] Confirm `services/core-api/tests/_factories/admin_users.py` exists with `make_user_with_profile`, `make_user_with_loyalty_and_profile`, `seed_admin_users_across_statuses`. Read-only.
- [x] 1.3 PREREQ: [core-api] Confirm reuse targets exist: `shared.models.{user, user_profile, loyalty_account, loyalty_transaction, order}`, `shared.enums.{UserStatus, OrderStatus, LoyaltyTransactionType}`, `core_api.services.order_cancel.cancel_order`, `core_api.rbac_matrix.{ADMIN, ROUTE_MATRIX, PUBLIC_ROUTES}`. Read-only.

## 2. GREEN — schemas module (`schemas/admin_users.py`)

- [x] 2.1 GREEN: [core-api] Create `services/core-api/src/core_api/schemas/admin_users.py` — declare 7 Pydantic v2 DTOs: `UserSummary`, `UserListResponse`, `LoyaltyTransactionItem`, `UserDetailResponse`, `BlockUserResponse`, `LoyaltyAdjustRequest` (with `Field(..., description="...")` for `delta` non-zero AND `min_length=1, max_length=500` on `reason`), `LoyaltyAdjustResponse`. All response DTOs use `ConfigDict(from_attributes=True)`. NO `phone`, `phone_hash`, or `deleted_at` fields anywhere. `LoyaltyAdjustRequest` uses a `@field_validator("delta")` that rejects `0`. Satisfies every body-shape assertion in RED 2.x/3.x/4.x/5.x/6.x + schema-422 tests 6.10–6.13.

## 3. GREEN — service module (`services/admin_users.py`) — errors + list

- [x] 3.1 GREEN: [core-api] Create `services/core-api/src/core_api/services/admin_users.py` — declare domain errors `AdminUsersError(Exception)`, `UserNotFoundError(AdminUsersError)`, `InvalidUserStateError(AdminUsersError)`, `InsufficientBalanceError(AdminUsersError)`. Satisfies RED imports in all 6 test modules.
- [x] 3.2 GREEN: [core-api] Extend `services/core-api/src/core_api/services/admin_users.py` — implement `list_users(db, *, status="all", search=None, page=1, per_page=20) -> UserListResponse` with SQL from design D3, status dispatch from D4, search predicate from D5, LEFT JOIN `user_profiles` and `loyalty_accounts`, `COALESCE(loyalty_accounts.balance, 0)`, ORDER BY `users.created_at DESC`, pagination via `.offset().limit()`, separate `total_count` query on filtered set (no join). Satisfies RED list tests 2.1–2.11.

## 4. GREEN — service module — detail

- [x] 4.1 GREEN: [core-api] Extend `services/core-api/src/core_api/services/admin_users.py` — implement `get_user_detail(db, user_id) -> UserDetailResponse` using 3 focused queries from design D6: (a) user + profile + loyalty_account with `joinedload`, raise `UserNotFoundError` on None OR when `user.deleted_at IS NOT NULL`; (b) last 20 `LoyaltyTransaction` ordered `created_at DESC`; (c) COUNT of orders where `status NOT IN (COMPLETED, CANCELLED)`. Set `language = profile.preferred_language if profile else "ru"`, `loyalty_balance = account.balance if account else 0`. Satisfies RED detail tests 3.1–3.9.

## 5. GREEN — service module — block

- [x] 5.1 GREEN: [core-api] Extend `services/core-api/src/core_api/services/admin_users.py` — implement `block_user(db, user_id) -> BlockUserResponse` per design D7+D8: `SELECT user FOR UPDATE`, raise `UserNotFoundError` on missing, raise `InvalidUserStateError("invalid_user_state")` on `{PENDING_VERIFICATION, DELETED}` or `deleted_at IS NOT NULL`, short-circuit to `cancelled_orders_count=0` on BLOCKED, otherwise flip to BLOCKED + `db.commit()`, SELECT orders in `{CREATED, PAID, PREPARING, READY}` (EXCLUDES IN_DELIVERY), for each call `cancel_order(order_id=o.id, cancelled_by="admin", reason="user_blocked", db_session=db)`, return count. Log warning when `count > 10`. Satisfies RED block tests 4.1–4.15.

## 6. GREEN — service module — unblock

- [x] 6.1 GREEN: [core-api] Extend `services/core-api/src/core_api/services/admin_users.py` — implement `unblock_user(db, user_id) -> BlockUserResponse` per design D9: `SELECT user FOR UPDATE`, raise `UserNotFoundError` on missing, raise `InvalidUserStateError("invalid_user_state")` on `{PENDING_VERIFICATION, DELETED}` or `deleted_at IS NOT NULL`, short-circuit to `status="active", cancelled_orders_count=0` on ACTIVE, otherwise flip to ACTIVE + `db.commit()`. No cascade. Satisfies RED unblock tests 5.1–5.13.

## 7. GREEN — service module — loyalty adjust

- [x] 7.1 GREEN: [core-api] Extend `services/core-api/src/core_api/services/admin_users.py` — implement `adjust_loyalty(db, user_id, delta, reason) -> LoyaltyAdjustResponse` per design D10: single transaction, `SELECT user FOR UPDATE` + `SELECT loyalty_account FOR UPDATE`, raise `UserNotFoundError` on missing user OR missing loyalty_account, raise `InvalidUserStateError("invalid_user_state")` on `{PENDING_VERIFICATION, DELETED}` or `deleted_at IS NOT NULL` (BLOCKED accepted), compute `new_balance = account.balance + delta`, raise `InsufficientBalanceError("insufficient_balance")` if `< 0`, UPDATE balance, INSERT `LoyaltyTransaction(type=ADMIN_ADJUSTMENT, amount=delta, balance_after=new_balance, description=reason, order_id=None)`, `db.flush()` for tx.id, `db.commit()`, return. Satisfies RED loyalty adjust tests 6.1–6.21.

## 8. GREEN — router module (`routers/admin_users.py`)

- [x] 8.1 GREEN: [core-api] Create `services/core-api/src/core_api/routers/admin_users.py` — instantiate `router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])`; define 5 handlers per design D11+D12: `list_admin_users` (Literal status query, `page ge=1`, `per_page ge=1 le=100`, `search max_length=100`, returns `UserListResponse`); `get_admin_user_detail(user_id: UUID)` (404 on `UserNotFoundError`, returns `UserDetailResponse`); `block_admin_user(user_id: UUID)` (404/409 mapping, returns `BlockUserResponse`); `unblock_admin_user(user_id: UUID)` (404/409 mapping, returns `BlockUserResponse`); `adjust_admin_user_loyalty(user_id: UUID, body: LoyaltyAdjustRequest)` (404/409/422 mapping, returns `LoyaltyAdjustResponse`). Error translation per design D11: `UserNotFoundError → 404`, `InvalidUserStateError → 409 detail="invalid_user_state"`, `InsufficientBalanceError → 422 detail="insufficient_balance"`. Satisfies RED route-registration tests (one per module) and RBAC 401/403 path tests plus happy-path response-body tests.

## 9. GREEN — RBAC matrix wiring

- [x] 9.1 GREEN: [core-api] Edit `services/core-api/src/core_api/rbac_matrix.py` — append five rows to `ROUTE_MATRIX`, each mapping to `{ADMIN}`: `("GET", "/api/v1/admin/users")`, `("GET", "/api/v1/admin/users/{user_id}")`, `("POST", "/api/v1/admin/users/{user_id}/block")`, `("POST", "/api/v1/admin/users/{user_id}/unblock")`, `("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust")`. Do NOT touch `PUBLIC_ROUTES`. Do NOT modify any existing row (guards `("GET", "/api/v1/profile")`, `("GET", "/api/v1/profile/loyalty")` stay `{CUSTOMER}`). Satisfies RED RBAC tests 7.1–7.8.

## 10. GREEN — register router in app

- [x] 10.1 GREEN: [core-api] Edit `services/core-api/src/core_api/main.py` — `from core_api.routers.admin_users import router as admin_users_router` and `app.include_router(admin_users_router)`. Place adjacent to the existing `admin_orders_router` include. Satisfies every RED route-registration guard across the 6 test modules.

## 11. VERIFY — RED suite flips green

- [x] 11.1 VERIFY: [core-api] Run `pytest services/core-api/tests/test_admin_users_list.py services/core-api/tests/test_admin_users_detail.py services/core-api/tests/test_admin_users_block.py services/core-api/tests/test_admin_users_unblock.py services/core-api/tests/test_admin_users_loyalty_adjust.py services/core-api/tests/test_admin_users_rbac.py -x -q` from the worktree stack. All 87 tests SHALL pass. (Actual: 90 passed.)
- [x] 11.2 VERIFY: [core-api] Run the full `services/core-api/tests/` suite — confirm no regression in pre-existing suites (auth, profile, orders, admin-orders, menu, cart, loyalty, promocode, checkout). Pre-existing failures on `feat/admin-users-api` (`test_route_cart`, `test_route_order_actions`, `test_route_order_history`, plus flaky `test_main_includes_menu_routers`, `test_delivery_assignment_state_machine`, `test_menu_admin`) are unrelated and did NOT grow in count (verified via stash-baseline diff).
- [x] 11.3 VERIFY: [core-api] `python3 -m py_compile services/core-api/src/core_api/services/admin_users.py services/core-api/src/core_api/schemas/admin_users.py services/core-api/src/core_api/routers/admin_users.py services/core-api/src/core_api/rbac_matrix.py services/core-api/src/core_api/main.py` returns SYNTAX_OK.
