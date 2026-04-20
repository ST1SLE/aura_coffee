## 1. PREREQ — Test factory infrastructure

- [x] 1.1 [core-api] PREREQ: Create `services/core-api/tests/_factories/admin_users.py` with helpers: `make_user_with_profile(session, *, status=UserStatus.ACTIVE, display_name=None, preferred_language="ru", created_at=None, deleted_at=None) -> User` (creates `User + UserProfile` row; random `phone_hash`, zero-length encrypted `phone` stub); `make_user_with_loyalty_and_profile(session, *, balance=0, **kwargs) -> tuple[User, LoyaltyAccount]` (stacks `LoyaltyAccount`); `seed_admin_users_across_statuses(session, counts: dict[UserStatus, int]) -> dict[UserStatus, list[UUID]]` (monotonic `created_at` spacing for deterministic DESC assertions). No tests yet — helpers are reused by admin-users test modules.

## 2. RED — list_users service tests

- [x] 2.1 [core-api] RED: Create `services/core-api/tests/test_admin_users_list.py::test_list_users_symbol_absent` — imports `from core_api.services.admin_users import list_users` inside the test body; asserts callable. Expected RED: `ImportError`.
- [x] 2.2 [core-api] RED: Add `test_list_users_status_all_includes_every_status_and_tombstones` — seeds users across `{ACTIVE, BLOCKED, PENDING_VERIFICATION, DELETED}` + one tombstoned ACTIVE; calls with `status="all"`; asserts every seeded user id appears in `items`.
- [x] 2.3 [core-api] RED: Add `test_list_users_status_active_excludes_tombstones` — seeds 2 ACTIVE + 1 tombstoned ACTIVE + 1 BLOCKED; calls with `status="active"`; asserts `len(items) == 2` and only non-tombstoned ACTIVE ids appear.
- [x] 2.4 [core-api] RED: Add `test_list_users_status_blocked_filters_exact` — seeds across all statuses; calls with `status="blocked"`; asserts every returned `item.status == "blocked"`.
- [x] 2.5 [core-api] RED: Add `test_list_users_status_pending_verification_filters_exact` — similar to 2.4 for `status="pending_verification"`.
- [x] 2.6 [core-api] RED: Add `test_list_users_status_deleted_returns_deleted_and_tombstones` — seeds 1 `DELETED` user + 1 tombstoned ACTIVE; calls with `status="deleted"`; asserts both appear in `items`.
- [x] 2.7 [core-api] RED: Add `test_list_users_search_prefix_matches_display_name_case_insensitively` — seeds users with `display_name` in `["Alice", "alicia", "Bob"]`; calls with `search="ali"`; asserts `len(items) == 2` and Bob is absent.
- [x] 2.8 [core-api] RED: Add `test_list_users_search_does_not_match_phone_hash_fragment` — seeds a user whose hex `phone_hash` begins with `"abcdef"` and `display_name="Valery"`; calls with `search="abc"`; asserts the user is NOT in returned `items` (INV-013 guard).
- [x] 2.9 [core-api] RED: Add `test_list_users_pagination_page_2_slices_rows_and_reports_total` — seeds 25 ACTIVE users; calls with `status="all", page=2, per_page=10`; asserts `total_count == 25` and `len(items) == 10`.
- [x] 2.10 [core-api] RED: Add `test_list_users_sort_is_created_at_desc` — seeds 3 users with `created_at` at T1<T2<T3; calls with `status="all"`; asserts returned id sequence equals `[T3, T2, T1]`.
- [x] 2.11 [core-api] RED: Add `test_list_users_loyalty_balance_coalesces_to_zero_when_account_absent` — seeds an ACTIVE user WITHOUT a `LoyaltyAccount`; calls with `status="active"`; asserts `item.loyalty_balance == 0`.
- [x] 2.12 [core-api] RED: Add `test_list_users_summary_has_no_phone_or_phone_hash_fields` — seeds one user; calls service; asserts `hasattr(item, "phone") is False` AND `hasattr(item, "phone_hash") is False` AND `"phone" not in item.model_dump()` AND `"phone_hash" not in item.model_dump()`.

## 3. RED — get_user_detail service tests

- [x] 3.1 [core-api] RED: Create `services/core-api/tests/test_admin_users_detail.py::test_get_user_detail_symbol_absent` — imports `from core_api.services.admin_users import get_user_detail` inside the test body; asserts callable. Expected RED: `ImportError`.
- [x] 3.2 [core-api] RED: Add `test_get_user_detail_user_not_found_error_symbol_absent` — imports `from core_api.services.admin_users import UserNotFoundError`; expected RED `ImportError`.
- [x] 3.3 [core-api] RED: Add `test_get_user_detail_happy_path_returns_merged_shape` — seeds ACTIVE user with `display_name="Alice"`, `preferred_language="en"`, loyalty balance 500, 5 loyalty transactions, 2 active orders + 3 completed orders; asserts returned `UserDetailResponse.status == "active"`, `.display_name == "Alice"`, `.language == "en"`, `.loyalty_balance == 500`, `.active_orders_count == 2`, `len(.loyalty_transactions) == 5`.
- [x] 3.4 [core-api] RED: Add `test_get_user_detail_returns_last_20_loyalty_transactions_desc` — seeds ACTIVE user with 25 loyalty transactions at monotonic `created_at`; asserts `len(loyalty_transactions) == 20`, ordered `created_at DESC`, and ids correspond to the most-recent 20.
- [x] 3.5 [core-api] RED: Add `test_get_user_detail_tombstone_raises_user_not_found` — seeds ACTIVE user + sets `deleted_at = now()`; asserts `get_user_detail` raises `UserNotFoundError`.
- [x] 3.6 [core-api] RED: Add `test_get_user_detail_unknown_id_raises_user_not_found` — calls with `uuid.uuid4()`; asserts `UserNotFoundError`.
- [x] 3.7 [core-api] RED: Add `test_get_user_detail_active_orders_count_excludes_completed_and_cancelled` — seeds one user with orders across `{CREATED, PAID, PREPARING, READY, IN_DELIVERY, COMPLETED, CANCELLED}`; asserts `active_orders_count == 5`.
- [x] 3.8 [core-api] RED: Add `test_get_user_detail_response_has_no_phone_or_phone_hash_or_deleted_at_fields` — seeds one user; asserts the Pydantic model dump JSON has no keys `phone`, `phone_hash`, `deleted_at`.
- [x] 3.9 [core-api] RED: Add `test_loyalty_transaction_item_omits_user_id_and_order_id` — imports `LoyaltyTransactionItem` from `core_api.schemas.admin_users`; asserts its model_fields set DOES NOT include `user_id` OR `order_id`.

## 4. RED — block_user service tests (+ route)

- [x] 4.1 [core-api] RED: Create `services/core-api/tests/test_admin_users_block.py::test_block_user_symbol_absent` — imports `from core_api.services.admin_users import block_user`; asserts callable. Expected RED: `ImportError`.
- [x] 4.2 [core-api] RED: Add `test_invalid_user_state_error_symbol_absent` — imports `from core_api.services.admin_users import InvalidUserStateError`; expected `ImportError`.
- [x] 4.3 [core-api] RED: Add `test_block_user_happy_path_with_three_active_orders` — seeds ACTIVE user with 3 orders `[CREATED, PAID, PREPARING]`; monkeypatches `core_api.services.order_cancel.celery_app.send_task` so no real Celery broker is hit; calls `block_user`; asserts `user.status == BLOCKED` in DB, all 3 order statuses are `CANCELLED`, and response is `BlockUserResponse(status="blocked", cancelled_orders_count=3)`.
- [x] 4.4 [core-api] RED: Add `test_block_user_completed_and_cancelled_orders_are_not_touched` — seeds ACTIVE user with orders `[PAID, COMPLETED, CANCELLED]`; monkeypatches celery; calls; asserts only the PAID order becomes CANCELLED (count=1) and COMPLETED stays COMPLETED, CANCELLED stays CANCELLED.
- [x] 4.5 [core-api] RED: Add `test_block_user_in_delivery_orders_are_skipped_silently` — seeds ACTIVE user with orders `[PAID, IN_DELIVERY]`; monkeypatches celery; calls; asserts response `cancelled_orders_count == 1` AND the IN_DELIVERY order remains IN_DELIVERY AND no `cancel_order` was called for it (spy via mock or check status).
- [x] 4.6 [core-api] RED: Add `test_block_user_idempotent_when_already_blocked` — seeds BLOCKED user with zero active orders; monkeypatches celery; calls; asserts `BlockUserResponse(status="blocked", cancelled_orders_count=0)` AND the celery `send_task` mock has NOT been called.
- [x] 4.7 [core-api] RED: Add `test_block_user_pending_verification_raises_invalid_state` — seeds PENDING_VERIFICATION user; calls; asserts raises `InvalidUserStateError` with message/arg `"invalid_user_state"`.
- [x] 4.8 [core-api] RED: Add `test_block_user_deleted_raises_invalid_state` — seeds user with `status=DELETED`; calls; asserts raises `InvalidUserStateError`.
- [x] 4.9 [core-api] RED: Add `test_block_user_tombstone_raises_invalid_state` — seeds ACTIVE user then sets `deleted_at=now()`; calls; asserts raises `InvalidUserStateError`.
- [x] 4.10 [core-api] RED: Add `test_block_user_route_not_registered` — inspects `app.routes` for a POST matching exactly `/api/v1/admin/users/{user_id}/block`; asserts count == 1 (GREEN target). Expected RED: count == 0.
- [x] 4.11 [core-api] RED: Add `test_block_user_route_rejects_no_auth` — uses `db_client` without headers to POST `/api/v1/admin/users/<uuid>/block`; asserts 401.
- [x] 4.12 [core-api] RED: Add `test_block_user_route_rejects_barista` — uses `db_client` with `barista_headers`; asserts 403.
- [x] 4.13 [core-api] RED: Add `test_block_user_route_happy_path_returns_200_and_count` — seeds ACTIVE user with 3 active orders; monkeypatches celery; sends POST with `admin_headers`; asserts 200 and `body["cancelled_orders_count"] == 3` and `body["status"] == "blocked"`.
- [x] 4.14 [core-api] RED: Add `test_block_user_route_409_on_pending_verification` — seeds PENDING_VERIFICATION user; sends POST; asserts 409 and `body["detail"] == "invalid_user_state"`.
- [x] 4.15 [core-api] RED: Add `test_block_user_route_404_on_unknown_user_id` — sends POST with random uuid; asserts 404.

## 5. RED — unblock_user service tests (+ route)

- [x] 5.1 [core-api] RED: Create `services/core-api/tests/test_admin_users_unblock.py::test_unblock_user_symbol_absent` — imports `from core_api.services.admin_users import unblock_user`; asserts callable. Expected RED: `ImportError`.
- [x] 5.2 [core-api] RED: Add `test_unblock_user_happy_path_flips_to_active` — seeds BLOCKED user; calls `unblock_user`; asserts `user.status == ACTIVE` in DB and response `BlockUserResponse(status="active", cancelled_orders_count=0)`.
- [x] 5.3 [core-api] RED: Add `test_unblock_user_idempotent_when_active` — seeds ACTIVE user; calls; asserts response `BlockUserResponse(status="active", cancelled_orders_count=0)` and DB status unchanged.
- [x] 5.4 [core-api] RED: Add `test_unblock_user_pending_verification_raises_invalid_state` — seeds PENDING_VERIFICATION user; asserts raises `InvalidUserStateError`.
- [x] 5.5 [core-api] RED: Add `test_unblock_user_deleted_raises_invalid_state` — seeds DELETED user; asserts raises `InvalidUserStateError`.
- [x] 5.6 [core-api] RED: Add `test_unblock_user_tombstone_raises_invalid_state` — seeds ACTIVE user then sets `deleted_at=now()`; asserts raises `InvalidUserStateError`.
- [x] 5.7 [core-api] RED: Add `test_unblock_user_does_not_resurrect_cancelled_orders` — seeds BLOCKED user with 2 CANCELLED orders; calls `unblock_user`; asserts user ACTIVE in DB AND both orders remain CANCELLED.
- [x] 5.8 [core-api] RED: Add `test_unblock_user_route_not_registered` — inspects `app.routes` for POST `/api/v1/admin/users/{user_id}/unblock`; asserts count == 1 (GREEN target). Expected RED: 0.
- [x] 5.9 [core-api] RED: Add `test_unblock_user_route_rejects_no_auth` — POST without headers; asserts 401.
- [x] 5.10 [core-api] RED: Add `test_unblock_user_route_rejects_customer` — POST with `customer_headers`; asserts 403.
- [x] 5.11 [core-api] RED: Add `test_unblock_user_route_happy_path_returns_200` — seeds BLOCKED user; POST with `admin_headers`; asserts 200 and `body["status"] == "active"`.
- [x] 5.12 [core-api] RED: Add `test_unblock_user_route_409_on_pending_verification` — seeds PENDING_VERIFICATION user; POST; asserts 409.
- [x] 5.13 [core-api] RED: Add `test_unblock_user_route_404_on_unknown_user_id` — POST with random uuid; asserts 404.

## 6. RED — adjust_loyalty service tests (+ route)

- [x] 6.1 [core-api] RED: Create `services/core-api/tests/test_admin_users_loyalty_adjust.py::test_adjust_loyalty_symbol_absent` — imports `from core_api.services.admin_users import adjust_loyalty`; expected `ImportError`.
- [x] 6.2 [core-api] RED: Add `test_insufficient_balance_error_symbol_absent` — imports `from core_api.services.admin_users import InsufficientBalanceError`; expected `ImportError`.
- [x] 6.3 [core-api] RED: Add `test_adjust_loyalty_positive_delta_credits_and_creates_admin_adjustment_transaction` — seeds ACTIVE user with loyalty balance=100; calls `adjust_loyalty(db, user_id, delta=500, reason="credit")`; asserts `account.balance == 600` in DB, a new `LoyaltyTransaction` with `type=ADMIN_ADJUSTMENT, amount=500, balance_after=600, description="credit", order_id IS NULL`; response `LoyaltyAdjustResponse(new_balance=600, delta=500)`.
- [x] 6.4 [core-api] RED: Add `test_adjust_loyalty_negative_delta_debits_balance` — seeds ACTIVE user with balance=500; calls with `delta=-200, reason="chargeback"`; asserts balance → 300, transaction amount=-200.
- [x] 6.5 [core-api] RED: Add `test_adjust_loyalty_insufficient_balance_raises_and_rolls_back` — seeds ACTIVE user with balance=100; calls with `delta=-200, reason="oops"`; asserts raises `InsufficientBalanceError("insufficient_balance")` AND `account.balance` remains 100 AND no new LoyaltyTransaction rows were inserted.
- [x] 6.6 [core-api] RED: Add `test_adjust_loyalty_blocked_user_is_accepted` — seeds BLOCKED user with balance=100; calls with `delta=200, reason="refund before unblock"`; asserts success, `new_balance=300`.
- [x] 6.7 [core-api] RED: Add `test_adjust_loyalty_pending_verification_raises_invalid_state` — seeds PENDING_VERIFICATION user + loyalty_account balance=0; calls with `delta=100, reason="x"`; asserts raises `InvalidUserStateError`.
- [x] 6.8 [core-api] RED: Add `test_adjust_loyalty_deleted_raises_invalid_state` — seeds DELETED user; asserts raises `InvalidUserStateError`.
- [x] 6.9 [core-api] RED: Add `test_adjust_loyalty_tombstone_raises_invalid_state` — seeds ACTIVE user with `deleted_at=now()`; asserts raises `InvalidUserStateError`.
- [x] 6.10 [core-api] RED: Add `test_adjust_loyalty_schema_rejects_delta_zero` — imports `LoyaltyAdjustRequest` from `core_api.schemas.admin_users`; tries `LoyaltyAdjustRequest(delta=0, reason="x")`; asserts `pydantic.ValidationError`.
- [x] 6.11 [core-api] RED: Add `test_adjust_loyalty_schema_rejects_empty_reason` — tries `LoyaltyAdjustRequest(delta=10, reason="")`; asserts `pydantic.ValidationError`.
- [x] 6.12 [core-api] RED: Add `test_adjust_loyalty_schema_rejects_reason_longer_than_500` — tries `LoyaltyAdjustRequest(delta=10, reason="x" * 501)`; asserts `pydantic.ValidationError`.
- [x] 6.13 [core-api] RED: Add `test_adjust_loyalty_route_not_registered` — inspects `app.routes` for POST `/api/v1/admin/users/{user_id}/loyalty/adjust`; asserts count == 1 (GREEN target). Expected RED: 0.
- [x] 6.14 [core-api] RED: Add `test_adjust_loyalty_route_rejects_no_auth` — POST without headers; asserts 401.
- [x] 6.15 [core-api] RED: Add `test_adjust_loyalty_route_rejects_non_admin_roles` — parametrised over `[barista_headers, courier_headers, customer_headers]`; POST each; asserts 403.
- [x] 6.16 [core-api] RED: Add `test_adjust_loyalty_route_happy_path_returns_200` — seeds ACTIVE user with balance=100; POST `{"delta": 500, "reason": "service credit"}` with `admin_headers`; asserts 200 AND `body["new_balance"] == 600` AND `body["delta"] == 500` AND `body["transaction_id"]` is a valid UUID string.
- [x] 6.17 [core-api] RED: Add `test_adjust_loyalty_route_422_on_delta_zero` — POST body `{"delta": 0, "reason": "x"}`; asserts 422.
- [x] 6.18 [core-api] RED: Add `test_adjust_loyalty_route_422_on_empty_reason` — POST `{"delta": 10, "reason": ""}`; asserts 422.
- [x] 6.19 [core-api] RED: Add `test_adjust_loyalty_route_422_on_long_reason` — POST `{"delta": 10, "reason": "x" * 501}`; asserts 422.
- [x] 6.20 [core-api] RED: Add `test_adjust_loyalty_route_422_on_insufficient_balance` — seeds ACTIVE user with balance=100; POST `{"delta": -200, "reason": "x"}`; asserts 422 AND `body["detail"]` mentions `"insufficient_balance"`.
- [x] 6.21 [core-api] RED: Add `test_adjust_loyalty_route_409_on_deleted_user` — seeds user with `deleted_at=now()`; POST any valid body; asserts 409.

## 7. RED — RBAC matrix + route absence tests

- [x] 7.1 [core-api] RED: Create `services/core-api/tests/test_admin_users_rbac.py::test_admin_users_list_row_is_admin_only` — asserts `ROUTE_MATRIX[("GET", "/api/v1/admin/users")] == {ADMIN}`. Expected RED: `KeyError`.
- [x] 7.2 [core-api] RED: Add `test_admin_users_detail_row_is_admin_only` — asserts `ROUTE_MATRIX[("GET", "/api/v1/admin/users/{user_id}")] == {ADMIN}`. Expected RED: `KeyError`.
- [x] 7.3 [core-api] RED: Add `test_admin_users_block_row_is_admin_only` — asserts `ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/block")] == {ADMIN}`. Expected RED: `KeyError`.
- [x] 7.4 [core-api] RED: Add `test_admin_users_unblock_row_is_admin_only` — asserts `ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/unblock")] == {ADMIN}`. Expected RED: `KeyError`.
- [x] 7.5 [core-api] RED: Add `test_admin_users_loyalty_adjust_row_is_admin_only` — asserts `ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust")] == {ADMIN}`. Expected RED: `KeyError`.
- [x] 7.6 [core-api] RED: Add `test_admin_users_routes_not_public` — asserts none of the five admin-users route tuples is in `PUBLIC_ROUTES`.
- [x] 7.7 [core-api] RED: Add `test_existing_customer_profile_row_untouched` — asserts `ROUTE_MATRIX[("GET", "/api/v1/profile")] == {CUSTOMER}`; guards against accidental role widening during GREEN.
- [x] 7.8 [core-api] RED: Add `test_existing_customer_profile_loyalty_row_untouched` — asserts `ROUTE_MATRIX[("GET", "/api/v1/profile/loyalty")] == {CUSTOMER}`.
- [x] 7.9 [core-api] RED: Add `test_admin_users_list_rejects_no_auth_route_level` in `test_admin_users_list.py` — uses `db_client` without headers on GET `/api/v1/admin/users`; asserts 401 (post-GREEN target).
- [x] 7.10 [core-api] RED: Add `test_admin_users_list_rejects_barista` — GET with `barista_headers`; asserts 403.
- [x] 7.11 [core-api] RED: Add `test_admin_users_list_rejects_courier` — GET with `courier_headers`; asserts 403.
- [x] 7.12 [core-api] RED: Add `test_admin_users_list_rejects_customer` — GET with `customer_headers`; asserts 403.
- [x] 7.13 [core-api] RED: Add `test_admin_users_detail_rejects_no_auth` — GET `/api/v1/admin/users/<uuid>` without headers; asserts 401.
- [x] 7.14 [core-api] RED: Add `test_admin_users_detail_rejects_non_admin_roles` — parametrised over `[barista_headers, courier_headers, customer_headers]`; GET `/api/v1/admin/users/<uuid>`; asserts 403.

## 8. VERIFY — RED suite is RED

- [x] 8.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_admin_users_list.py services/core-api/tests/test_admin_users_detail.py services/core-api/tests/test_admin_users_block.py services/core-api/tests/test_admin_users_unblock.py services/core-api/tests/test_admin_users_loyalty_adjust.py services/core-api/tests/test_admin_users_rbac.py -v` and confirm every new test fails (mix of `ImportError`, `KeyError`, assertion, or 401/403/404/422 mismatches) while the rest of the suite still passes. Record the failing test count.
- [x] 8.2 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/ -q --ignore=services/core-api/tests/test_admin_users_list.py --ignore=services/core-api/tests/test_admin_users_detail.py --ignore=services/core-api/tests/test_admin_users_block.py --ignore=services/core-api/tests/test_admin_users_unblock.py --ignore=services/core-api/tests/test_admin_users_loyalty_adjust.py --ignore=services/core-api/tests/test_admin_users_rbac.py` to confirm no regression in pre-existing tests (admin-orders-api, admin-promocodes-api, order-history, profile, etc. all remain green).
