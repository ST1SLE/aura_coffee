## 1. PREREQ — verify RED artefacts landed

- [x] 1.1 PREREQ: [core-api] Убедиться, что `tests/test_profile_loyalty_balance.py`, `tests/test_profile_loyalty_transactions.py`, `tests/test_profile_loyalty_rbac.py`, `tests/_factories/loyalty.py` присутствуют в worktree (закоммичены `customer-loyalty-api-red`). Read-only.
- [x] 1.2 PREREQ: [core-api] Убедиться, что target-модули отсутствуют: `core_api.services.loyalty`, `core_api.schemas.loyalty`, `core_api.routers.profile_loyalty` (GREEN их создаст).

## 2. GREEN — Pydantic schemas

- [x] 2.1 GREEN: [core-api] Создать `services/core-api/src/core_api/schemas/loyalty.py` с тремя моделями: `LoyaltyBalanceResponse(balance, lifetime_accrued)`, `LoyaltyTransactionResponse(id, type, amount, balance_after, order_id, description, created_at; model_config=ConfigDict(from_attributes=True))`, `LoyaltyTransactionListResponse(items, page, per_page, total)`. `type: LoyaltyTransactionType` из `shared.enums`. Удовлетворяет RED-тесты 4.1–4.5.

## 3. GREEN — Service module

- [x] 3.1 GREEN: [core-api] Создать `services/core-api/src/core_api/services/loyalty.py` с классом `LoyaltyAccountMissingError(Exception)`. Satisfies RED-тест 2.4.
- [x] 3.2 GREEN: [core-api] В том же модуле — `get_balance(*, user_id: UUID, db_session: Session) -> LoyaltyBalanceResponse`: `db_session.get(LoyaltyAccount, user_id)`; если None → поднять `LoyaltyAccountMissingError`; `SUM(amount) WHERE user_id=:user_id AND type=ACCRUAL` через `COALESCE(sum(...), 0)`; вернуть `LoyaltyBalanceResponse`. Satisfies 2.1, 2.2, 2.3, 2.5, 5.6.
- [x] 3.3 GREEN: [core-api] В том же модуле — `list_transactions(*, user_id: UUID, page: int, per_page: int, db_session: Session) -> LoyaltyTransactionListResponse`: COUNT + SELECT c `order_by(LoyaltyTransaction.created_at.desc())` + offset/limit; `LoyaltyTransactionResponse.model_validate(row)` для каждого row. Satisfies 3.1–3.7.

## 4. GREEN — Router module

- [x] 4.1 GREEN: [core-api] Создать `services/core-api/src/core_api/routers/profile_loyalty.py`:
  - `APIRouter(prefix="/api/v1/profile/loyalty", tags=["loyalty"])`.
  - `_get_session()` обёртка над `core_api.deps.database.get_session` (patch-friendly).
  - `get_my_loyalty_balance(current_user=Depends(get_current_user), db=Depends(_get_session))` → `get_balance(...)`; ловит `LoyaltyAccountMissingError` → `HTTPException(500, detail="loyalty_account_missing")`.
  - `list_my_loyalty_transactions(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user), db=Depends(_get_session))` → `list_transactions(...)`.
  - `response_model` на каждом route.
  Satisfies 5.1–5.6 и 6.1–6.8 (router-part).

## 5. GREEN — RBAC matrix

- [x] 5.1 GREEN: [core-api] Добавить две строки в `core_api/rbac_matrix.py::ROUTE_MATRIX`:
  - `("GET", "/api/v1/profile/loyalty"): {CUSTOMER}`.
  - `("GET", "/api/v1/profile/loyalty/transactions"): {CUSTOMER}`.
  Не трогать `PUBLIC_ROUTES`, не менять существующие строки. Satisfies 8.1, 8.2, 8.3, 8.4, 8.5, и meta-тест test_route_coverage.

## 6. GREEN — include router in main.py

- [x] 6.1 GREEN: [core-api] В `core_api/main.py`: `from core_api.routers.profile_loyalty import router as profile_loyalty_router`; `app.include_router(profile_loyalty_router)` рядом с `profile_router` / `delivery_addresses_router`. Satisfies 5.1, 6.1.

## 7. VERIFY — suite green

- [x] 7.1 VERIFY: [core-api] `docker compose exec core-api pytest services/core-api/tests/test_profile_loyalty_balance.py services/core-api/tests/test_profile_loyalty_transactions.py services/core-api/tests/test_profile_loyalty_rbac.py -v` — все тесты PASS.
- [x] 7.2 VERIFY: [core-api] Full suite `docker compose exec core-api pytest services/core-api/tests/ -q` — нет regression (особенно `test_route_coverage`, `test_rbac_matrix`, `test_profile_endpoints`, `test_admin_orders_*`).
- [x] 7.3 VERIFY: [core-api] `python3 -m py_compile` для четырёх изменённых файлов (`schemas/loyalty.py`, `services/loyalty.py`, `routers/profile_loyalty.py`, `main.py`) — синтаксис валиден.
