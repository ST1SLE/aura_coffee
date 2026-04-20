## 1. PREREQ — test infrastructure helper

- [x] 1.1 [core-api] PREREQ: Add `seed_loyalty_account(session, *, user, balance)` and `seed_loyalty_transaction(session, *, user, type, amount, balance_after, order_id=None, description=None, created_at=None)` helpers into a new `services/core-api/tests/_factories/loyalty.py`. Also add `make_user_with_loyalty(session, *, balance=0)` — создаёт `User(ACTIVE)` + связанный `LoyaltyAccount(balance=...)`. Helpers использует `sqlalchemy.orm.Session` и возвращают созданные ORM-объекты. No tests in this task — consumed by 2.x/3.x/4.x/5.x test modules.

## 2. RED — `services.loyalty.get_balance` service tests

- [x] 2.1 [core-api] RED: Create `services/core-api/tests/test_profile_loyalty_balance.py::test_get_balance_symbol_absent` — `from core_api.services.loyalty import get_balance` impotet inside the test body; `assert callable(get_balance)`. RED: `ImportError`.
- [x] 2.2 [core-api] RED: Add `test_get_balance_returns_account_balance_and_lifetime_from_accrual_only` — seed user A, LoyaltyAccount(balance=500), транзакции ACCRUAL 100, ACCRUAL 200, ACCRUAL 50, REDEMPTION -30, REVERSAL -50; call `get_balance(user_id=A.id, db_session=db_session)`; assert `result.balance == 500`, `result.lifetime_accrued == 350`.
- [x] 2.3 [core-api] RED: Add `test_get_balance_zero_for_new_user` — seed `make_user_with_loyalty(balance=0)` без транзакций; assert `balance == 0`, `lifetime_accrued == 0`.
- [x] 2.4 [core-api] RED: Add `test_get_balance_raises_when_account_row_missing` — создать User ACTIVE БЕЗ LoyaltyAccount; assert `LoyaltyAccountMissingError` (import из `core_api.services.loyalty`).
- [x] 2.5 [core-api] RED: Add `test_get_balance_isolates_users` — user A: balance=100, ACCRUAL=100; user B: balance=9999, ACCRUAL=9999; call `get_balance(user_id=A.id, ...)`; assert `balance==100`, `lifetime_accrued==100` (user B данные не утекают).

## 3. RED — `services.loyalty.list_transactions` service tests

- [x] 3.1 [core-api] RED: Create `services/core-api/tests/test_profile_loyalty_transactions.py::test_list_transactions_symbol_absent` — `from core_api.services.loyalty import list_transactions` inside test body; `assert callable(list_transactions)`. RED: `ImportError`.
- [x] 3.2 [core-api] RED: Add `test_list_transactions_sorts_created_at_desc` — user A, LoyaltyAccount; seed 3 ACCRUAL транзакции с `created_at` T1 < T2 < T3; call `list_transactions(user_id=A.id, page=1, per_page=20, db_session=...)`; assert `[item.id for item in result.items] == [t3_id, t2_id, t1_id]`.
- [x] 3.3 [core-api] RED: Add `test_list_transactions_pagination_slice_and_total` — 25 транзакций для user A с монотонным created_at; call с `page=2, per_page=10`; assert `result.total == 25`, `len(result.items) == 10`; id последовательность — DESC-ранг 11..20.
- [x] 3.4 [core-api] RED: Add `test_list_transactions_contains_all_four_types` — user A, по одной транзакции каждого типа (ACCRUAL, REDEMPTION, REVERSAL, ADMIN_ADJUSTMENT); call; assert `{item.type for item in result.items}` содержит все 4 значения `LoyaltyTransactionType`.
- [x] 3.5 [core-api] RED: Add `test_list_transactions_admin_adjustment_has_null_order_id` — создать ADMIN_ADJUSTMENT с `order_id=None`; call; найти row по `type == ADMIN_ADJUSTMENT`; assert `item.order_id is None`.
- [x] 3.6 [core-api] RED: Add `test_list_transactions_empty_history` — user A с LoyaltyAccount, без транзакций; call; assert `result.total == 0`, `result.items == []`.
- [x] 3.7 [core-api] RED: Add `test_list_transactions_isolates_users` — user A: 2 транзакции; user B: 3 транзакции; call `list_transactions(user_id=A.id, ...)`; assert `result.total == 2` и набор `{item.id for item in result.items}` ⊆ id транзакций user A, не пересекается с user B.

## 4. RED — Pydantic schema tests

- [x] 4.1 [core-api] RED: Add to `test_profile_loyalty_balance.py::test_balance_schema_module_absent` — `from core_api.schemas.loyalty import LoyaltyBalanceResponse` inside test body; assert class. RED: `ImportError`.
- [x] 4.2 [core-api] RED: Add `test_balance_schema_fields` — import `LoyaltyBalanceResponse`; instantiate `LoyaltyBalanceResponse(balance=500, lifetime_accrued=350)`; assert `.balance == 500`, `.lifetime_accrued == 350`; verify field set via `model_fields.keys()`.
- [x] 4.3 [core-api] RED: Add to `test_profile_loyalty_transactions.py::test_transaction_schema_module_absent` — `from core_api.schemas.loyalty import LoyaltyTransactionResponse, LoyaltyTransactionListResponse` inside test body; assert classes. RED: `ImportError`.
- [x] 4.4 [core-api] RED: Add `test_transaction_schema_has_required_fields` — inspect `LoyaltyTransactionResponse.model_fields` — assert ключи `{id, type, amount, balance_after, order_id, description, created_at}` все присутствуют.
- [x] 4.5 [core-api] RED: Add `test_transaction_list_schema_has_required_fields` — inspect `LoyaltyTransactionListResponse.model_fields` — assert ключи `{items, page, per_page, total}`.

## 5. RED — GET /api/v1/profile/loyalty router tests

- [x] 5.1 [core-api] RED: Add `test_balance_route_not_registered` to `test_profile_loyalty_balance.py` — inspect `app.routes` for GET exactly `/api/v1/profile/loyalty`; assert match count == 1 (GREEN target). RED: count == 0.
- [x] 5.2 [core-api] RED: Add `test_balance_requires_authorization` — client без headers шлёт `GET /api/v1/profile/loyalty`; assert 401.
- [x] 5.3 [core-api] RED: Add `test_balance_rejects_admin` — `admin_headers`; assert 403.
- [x] 5.4 [core-api] RED: Add `test_balance_rejects_barista` — `barista_headers`; assert 403.
- [x] 5.5 [core-api] RED: Add `test_balance_rejects_courier` — `courier_headers`; assert 403.
- [x] 5.6 [core-api] RED: Add `test_balance_returns_balance_and_lifetime_for_customer` — используя `tests/_helpers/jwt.auth_headers_for_user(user_a.id, "customer")` с реальным user A в БД, LoyaltyAccount(balance=500), ACCRUAL транзакции на сумму 350; `client.get("/api/v1/profile/loyalty", headers=...)`; assert 200, body == `{"balance": 500, "lifetime_accrued": 350}`.

## 6. RED — GET /api/v1/profile/loyalty/transactions router tests

- [x] 6.1 [core-api] RED: Add `test_transactions_route_not_registered` to `test_profile_loyalty_transactions.py` — inspect `app.routes` for `/api/v1/profile/loyalty/transactions`; assert match count == 1.
- [x] 6.2 [core-api] RED: Add `test_transactions_requires_authorization` — без headers; assert 401.
- [x] 6.3 [core-api] RED: Add `test_transactions_rejects_admin` / `..._rejects_barista` / `..._rejects_courier` — три теста; каждый assert 403.
- [x] 6.4 [core-api] RED: Add `test_transactions_rejects_per_page_over_100` — customer JWT, `?per_page=101`; assert 422.
- [x] 6.5 [core-api] RED: Add `test_transactions_returns_items_sorted_desc_with_pagination` — user A в БД + 25 транзакций; JWT с `sub=user_a.id`; `client.get("/api/v1/profile/loyalty/transactions?page=2&per_page=10")`; assert 200, `body["total"] == 25`, `body["page"] == 2`, `body["per_page"] == 10`, `len(body["items"]) == 10`, DESC-ранг matches 11..20.
- [x] 6.6 [core-api] RED: Add `test_transactions_body_contains_all_four_types` — 4 транзакции разных типов для user A; assert `{item["type"] for item in body["items"]}` == 4 значения.
- [x] 6.7 [core-api] RED: Add `test_transactions_admin_adjustment_order_id_is_null` — создать ADMIN_ADJUSTMENT с order_id=None; assert соответствующий item в body имеет `"order_id": None`.
- [x] 6.8 [core-api] RED: Add `test_transactions_empty_history_returns_empty_list` — user A без транзакций; assert 200, `body["total"] == 0`, `body["items"] == []`.

## 7. RED — isolation test (user A не видит транзакции user B)

- [x] 7.1 [core-api] RED: Create `services/core-api/tests/test_profile_loyalty_rbac.py::test_user_A_cannot_see_user_B_transactions` — seed user A (2 транзакции) и user B (3 транзакции) в одной БД; JWT `auth_headers_for_user(user_a.id, "customer")`; `client.get("/api/v1/profile/loyalty/transactions")`; assert status 200, `body["total"] == 2`, `len(body["items"]) == 2`, и `{item["id"] for item in body["items"]} ⊆ {str(t.id) for t in user_a_transactions}`, disjoint с set id user B. Этот тест закрывает INV-010 end-to-end.

## 8. RED — RBAC matrix + PUBLIC_ROUTES + existing rows preserved

- [x] 8.1 [core-api] RED: Add to `test_profile_loyalty_rbac.py::test_balance_matrix_row_allows_customer_only` — `assert ROUTE_MATRIX[("GET", "/api/v1/profile/loyalty")] == {CUSTOMER}`. RED: `KeyError`.
- [x] 8.2 [core-api] RED: Add `test_transactions_matrix_row_allows_customer_only` — `assert ROUTE_MATRIX[("GET", "/api/v1/profile/loyalty/transactions")] == {CUSTOMER}`.
- [x] 8.3 [core-api] RED: Add `test_loyalty_routes_not_in_public_routes` — assert `("GET", "/api/v1/profile/loyalty") not in PUBLIC_ROUTES` и `("GET", "/api/v1/profile/loyalty/transactions") not in PUBLIC_ROUTES`.
- [x] 8.4 [core-api] RED: Add `test_existing_profile_get_matrix_row_untouched` — `assert CUSTOMER in ROUTE_MATRIX[("GET", "/api/v1/profile")]`.
- [x] 8.5 [core-api] RED: Add `test_balance_rejects_admin_barista_courier_rbac_matrix` — `assert ADMIN not in ROUTE_MATRIX.get(("GET","/api/v1/profile/loyalty"), set())` и аналогично для BARISTA/COURIER (после GREEN это остаётся справедливым).

## 9. VERIFY — RED suite fails as expected

- [x] 9.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_profile_loyalty_balance.py services/core-api/tests/test_profile_loyalty_transactions.py services/core-api/tests/test_profile_loyalty_rbac.py -v` и убедиться, что КАЖДЫЙ новый тест падает (смесь `ImportError`, `KeyError`, assertion, 401/403). Все pre-existing тесты (`test_route_coverage`, `test_profile_endpoints`, `test_admin_orders_*`) ДОЛЖНЫ оставаться зелёными. Записать failing count в apply-log.
