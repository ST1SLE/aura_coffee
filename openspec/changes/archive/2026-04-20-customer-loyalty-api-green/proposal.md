## Why

RED-фаза `customer-loyalty-api-red` зафиксировала контракт customer-scoped read-only loyalty API failing-тестами (28 fail). Сейчас нужна минимальная реализация, которая делает эти тесты зелёными: сервис, схемы, router, RBAC-wiring.

MVP phase: **Phase 5 — Loyalty & Promocodes** (PDD §7.1 item 2).

## What Changes

- Создать `core_api/schemas/loyalty.py` с тремя Pydantic v2 моделями:
  - `LoyaltyBalanceResponse(balance: int, lifetime_accrued: int)`.
  - `LoyaltyTransactionResponse(id, type, amount, balance_after, order_id, description, created_at)` — `model_config = ConfigDict(from_attributes=True)`.
  - `LoyaltyTransactionListResponse(items, page, per_page, total)`.
- Создать `core_api/services/loyalty.py`:
  - `class LoyaltyAccountMissingError(Exception)` — data-integrity error (500 на API).
  - `get_balance(*, user_id, db_session)` — SELECT balance + aggregate SUM(amount) WHERE type='accrual'.
  - `list_transactions(*, user_id, page, per_page, db_session)` — фильтрация по user_id + SUM count + DESC срез.
- Создать `core_api/routers/profile_loyalty.py`:
  - `APIRouter(prefix="/api/v1/profile/loyalty", tags=["loyalty"])`.
  - Handler `get_my_loyalty_balance` — читает user_id из request.state (JWT middleware) → сервис → response.
  - Handler `list_my_loyalty_transactions` с `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=100)`.
  - Ошибка `LoyaltyAccountMissingError` → `HTTPException(500)`.
- Дополнить `core_api/rbac_matrix.py`:
  - `("GET", "/api/v1/profile/loyalty")` → `{CUSTOMER}`.
  - `("GET", "/api/v1/profile/loyalty/transactions")` → `{CUSTOMER}`.
- Включить router в `core_api/main.py` рядом с остальными profile-router-ами.
- Ничего больше не модифицируется: существующий `/api/v1/profile`, `list_orders`, mutations Phase 3.

## Capabilities

### New Capabilities
- `customer-loyalty-api`: Customer-scoped read-only surface лояльности — balance + paginated transactions feed.

### Modified Capabilities
<!-- None — GREEN реализует то, что RED зафиксировал. -->

## Non-Goals

- Мутационные endpoint-ы (redeem, accrue, reversal).
- ADMIN_ADJUSTMENT UI (Phase 6 users management).
- Денормализация `lifetime_accrued` в колонку loyalty_accounts.
- Дополнительные query-параметры (фильтр по type/диапазону дат) — не требуется MVP.
- Конвертация баллов в копейки на API-boundary.
- Миграции — никаких новых таблиц или индексов.
- Frontend (customer loyalty UI — отдельная web-customer change).

## Impact

- **Code**: новые файлы `services/core-api/src/core_api/schemas/loyalty.py`, `services/loyalty.py`, `routers/profile_loyalty.py`; правки в `rbac_matrix.py` (+2 строки) и `main.py` (+include_router).
- **APIs**: реализует `GET /api/v1/profile/loyalty` и `GET /api/v1/profile/loyalty/transactions`.
- **Dependencies**: `shared.models.loyalty_account.LoyaltyAccount`, `shared.models.loyalty_transaction.LoyaltyTransaction`, `shared.enums.LoyaltyTransactionType`, существующие `core_api.deps.database`.
- **Inviolable rules touched**: INV-002 (авторизация), INV-010 (role isolation — сервис фильтрует по user_id), INV-013 (user_id — opaque UUID из JWT sub).
- **Systems**: PostgreSQL (SELECT + aggregate). Без миграций, без Redis, без Celery.
