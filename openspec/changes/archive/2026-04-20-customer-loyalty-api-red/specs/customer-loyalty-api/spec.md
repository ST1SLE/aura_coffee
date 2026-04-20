## ADDED Requirements

_References: PDD §3 Loyalty Account / Loyalty Transaction, §5.2 Лояльность (модель данных), §5.4 индексы (`loyalty_transactions(user_id, created_at DESC)`), §7.1 Phase 5 item 2, INV-002 (auth для mutations), INV-003 (роль customer), INV-010 (изоляция ролей — customer видит только свои данные), INV-013 (PII: user_id — opaque UUID)._

### Requirement: Customer-scoped balance service

The system SHALL expose a service function `get_balance(*, user_id: UUID, db_session: Session) -> LoyaltyBalanceResponse` at `core_api.services.loyalty`. The service MUST:

- SELECT `loyalty_accounts.balance` filtered strictly by the passed `user_id` (INV-002, INV-010 — не полагается на API-handler).
- Aggregate `SUM(loyalty_transactions.amount)` WHERE `user_id = :user_id AND type = 'accrual'` для `lifetime_accrued`. REVERSAL/REDEMPTION/ADMIN_ADJUSTMENT НЕ учитываются в lifetime.
- Вернуть `LoyaltyBalanceResponse(balance=<int>, lifetime_accrued=<int>)`. Баллы — ШТУКИ (1 балл = 1₽), никакой конвертации в копейки.
- Если `loyalty_accounts` row отсутствует — поднять выделенный domain error (`LoyaltyAccountMissingError` или эквивалент) — это data-integrity issue, row обязан быть создан при ACTIVE-регистрации в Phase 1.
- Если агрегат SUM возвращает NULL (нет accrual-транзакций) — `lifetime_accrued` SHALL be 0.

В RED-change этот символ MUST NOT exist.

#### Scenario: RED — balance service symbol is absent
- **WHEN** тест выполняет `from core_api.services.loyalty import get_balance`
- **THEN** импорт SHALL поднять `ImportError` / `ModuleNotFoundError`

#### Scenario: Balance returns account balance and accrual-only lifetime
- **GIVEN** loyalty_accounts row user A с balance=500; loyalty_transactions для user A: ACCRUAL 100, ACCRUAL 200, ACCRUAL 50, REDEMPTION -30, REVERSAL -50
- **WHEN** сервис вызывается с `user_id=A`
- **THEN** `balance == 500` AND `lifetime_accrued == 350` (сумма только ACCRUAL rows)

#### Scenario: Zero-balance customer without transactions
- **GIVEN** loyalty_accounts row user A с balance=0, без loyalty_transactions
- **WHEN** сервис вызывается
- **THEN** `balance == 0` AND `lifetime_accrued == 0`

#### Scenario: Missing loyalty_accounts row raises domain error
- **GIVEN** user A в таблице users, но БЕЗ loyalty_accounts row
- **WHEN** сервис вызывается с `user_id=A`
- **THEN** поднимается designated `LoyaltyAccountMissingError` (data-integrity issue)

#### Scenario: Cross-user isolation (INV-010)
- **GIVEN** user A: balance=100, ACCRUAL=100; user B: balance=9999, ACCRUAL=9999
- **WHEN** сервис вызывается с `user_id=A`
- **THEN** возвращает `balance=100, lifetime_accrued=100` — значения user B не просачиваются

### Requirement: Customer-scoped transactions list service

The system SHALL expose a service function `list_transactions(*, user_id: UUID, page: int, per_page: int, db_session: Session) -> LoyaltyTransactionListResponse` at `core_api.services.loyalty`. The service MUST:

- Фильтровать `loyalty_transactions.user_id = :user_id` (INV-002, INV-010 — сервис обязан фильтровать сам, не доверяя handler-у).
- Поддерживать все 4 значения `LoyaltyTransactionType`: `ACCRUAL`, `REDEMPTION`, `REVERSAL`, `ADMIN_ADJUSTMENT`.
- `amount` — integer, может быть отрицательным (REDEMPTION).
- `order_id` может быть `NULL` (случай ADMIN_ADJUSTMENT).
- Сортировать `ORDER BY created_at DESC` (использует индекс `loyalty_transactions(user_id, created_at DESC)` из PDD §5.4).
- Пагинировать: `page >= 1`, `per_page in [1, 100]`. Использовать `OFFSET/LIMIT = (page-1)*per_page / per_page`.
- Возвращать `total` — полный счёт (игнорируя page/per_page), а также echo'd `page` и `per_page`.
- При отсутствии истории — вернуть `items=[]`, `total=0`.

В RED-change этот символ MUST NOT exist.

#### Scenario: RED — transactions service symbol is absent
- **WHEN** тест выполняет `from core_api.services.loyalty import list_transactions`
- **THEN** импорт SHALL поднять `ImportError` / `ModuleNotFoundError`

#### Scenario: Sort is created_at DESC
- **GIVEN** для user A созданы 3 ACCRUAL транзакции с `created_at` T1 < T2 < T3
- **WHEN** вызван `list_transactions(user_id=A, page=1, per_page=20)`
- **THEN** `items` расположены в порядке `[T3, T2, T1]` (id matching T3 first)

#### Scenario: Pagination yields exact slice and stable total
- **GIVEN** 25 транзакций для user A
- **WHEN** вызван `list_transactions(user_id=A, page=2, per_page=10)`
- **THEN** `total == 25` AND `len(items) == 10` AND slice соответствует DESC-rank 11..20

#### Scenario: All four transaction types are represented
- **GIVEN** для user A созданы по одной транзакции каждого типа (ACCRUAL, REDEMPTION, REVERSAL, ADMIN_ADJUSTMENT)
- **WHEN** вызван `list_transactions(user_id=A, page=1, per_page=20)`
- **THEN** `{item.type for item in items}` SHALL include все 4 значения `LoyaltyTransactionType`

#### Scenario: ADMIN_ADJUSTMENT row exposes order_id=null
- **GIVEN** для user A создана ADMIN_ADJUSTMENT транзакция с `order_id=NULL`
- **WHEN** вызван `list_transactions(user_id=A, page=1, per_page=20)`
- **THEN** соответствующий `item.order_id` SHALL равняться `None`

#### Scenario: Empty history
- **GIVEN** user A без loyalty_transactions
- **WHEN** вызван `list_transactions(user_id=A, page=1, per_page=20)`
- **THEN** `total == 0` AND `items == []`

#### Scenario: Cross-user isolation (INV-010)
- **GIVEN** user A: 2 транзакции; user B: 3 транзакции
- **WHEN** вызван `list_transactions(user_id=A, page=1, per_page=20)`
- **THEN** `total == 2` AND для каждого item в items он соответствует транзакции user A — транзакции user B отсутствуют

### Requirement: Pydantic schemas at `core_api.schemas.loyalty`

Модуль `core_api.schemas.loyalty` SHALL определить три Pydantic v2 модели:

- `LoyaltyBalanceResponse`: `balance: int`, `lifetime_accrued: int`.
- `LoyaltyTransactionResponse` (model_config `from_attributes=True`):
  - `id: UUID`
  - `type: LoyaltyTransactionType` (enum из `shared.enums`)
  - `amount: int` (может быть отрицательным)
  - `balance_after: int`
  - `order_id: UUID | None` (null для ADMIN_ADJUSTMENT)
  - `description: str | None`
  - `created_at: datetime`
- `LoyaltyTransactionListResponse`: `items: list[LoyaltyTransactionResponse]`, `page: int`, `per_page: int`, `total: int`.

В RED-change модуль MUST NOT exist.

#### Scenario: RED — schemas module is absent
- **WHEN** тест выполняет `from core_api.schemas.loyalty import LoyaltyBalanceResponse`
- **THEN** импорт SHALL поднять `ImportError` / `ModuleNotFoundError`

### Requirement: GET /api/v1/profile/loyalty endpoint

The system SHALL expose `GET /api/v1/profile/loyalty` at `core_api.routers.profile_loyalty`. Route MUST:

- Требовать Bearer JWT с ролью CUSTOMER; admin/barista/courier → 403; без токена → 401 (RBAC middleware по матрице).
- Извлекать `user_id` из `sub` JWT, делегировать в `services.loyalty.get_balance(user_id=..., db_session=...)`.
- Возвращать `LoyaltyBalanceResponse` с полями `balance` и `lifetime_accrued`.
- При `LoyaltyAccountMissingError` от сервиса — отвечать HTTP 500 (data-integrity).

В RED-change маршрут MUST NOT быть зарегистрирован.

#### Scenario: RED — route is not registered
- **WHEN** тест инспектирует `app.routes` на GET, совпадающий с `/api/v1/profile/loyalty`
- **THEN** количество совпадений SHALL равняться 0

#### Scenario: 401 without Authorization header
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty` без `Authorization`
- **THEN** статус SHALL быть 401

#### Scenario: 403 for admin role
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty` с JWT роли `admin`
- **THEN** статус SHALL быть 403

#### Scenario: 403 for barista role
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty` с JWT роли `barista`
- **THEN** статус SHALL быть 403

#### Scenario: 403 for courier role
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty` с JWT роли `courier`
- **THEN** статус SHALL быть 403

#### Scenario: Customer sees own balance and lifetime_accrued
- **GIVEN** user A с balance=500 и ACCRUAL-транзакциями на сумму 350; JWT-token с `sub=A.id` и role=customer
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty`
- **THEN** ответ SHALL быть 200 с телом `{"balance": 500, "lifetime_accrued": 350}`

### Requirement: GET /api/v1/profile/loyalty/transactions endpoint

The system SHALL expose `GET /api/v1/profile/loyalty/transactions` at `core_api.routers.profile_loyalty`. Query parameters:

- `page: int = Query(1, ge=1)`.
- `per_page: int = Query(20, ge=1, le=100)` — свыше 100 → 422.

Маршрут MUST:

- Требовать Bearer JWT с ролью CUSTOMER; admin/barista/courier → 403; без токена → 401.
- Извлекать `user_id` из JWT, делегировать в `services.loyalty.list_transactions(user_id=..., page=..., per_page=..., db_session=...)`.
- Возвращать `LoyaltyTransactionListResponse`.
- СТРОГО фильтровать по собственному `user_id` — клиент A не видит транзакции клиента B (INV-010). Сервис тоже фильтрует (defence-in-depth).

В RED-change маршрут MUST NOT быть зарегистрирован.

#### Scenario: RED — route is not registered
- **WHEN** тест инспектирует `app.routes` на GET, совпадающий с `/api/v1/profile/loyalty/transactions`
- **THEN** количество совпадений SHALL равняться 0

#### Scenario: 401 without Authorization header
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions` без заголовка
- **THEN** статус SHALL быть 401

#### Scenario: 403 for admin role
- **WHEN** клиент шлёт запрос с JWT роли admin
- **THEN** статус SHALL быть 403

#### Scenario: 403 for barista role
- **WHEN** клиент шлёт запрос с JWT роли barista
- **THEN** статус SHALL быть 403

#### Scenario: 403 for courier role
- **WHEN** клиент шлёт запрос с JWT роли courier
- **THEN** статус SHALL быть 403

#### Scenario: 422 when per_page exceeds 100
- **WHEN** клиент с customer JWT шлёт `GET /api/v1/profile/loyalty/transactions?per_page=101`
- **THEN** статус SHALL быть 422

#### Scenario: Customer sees only own transactions (isolation)
- **GIVEN** user A: 2 транзакции; user B: 3 транзакции; JWT с `sub=A.id`, role=customer
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions`
- **THEN** статус 200, `total == 2`, `len(items) == 2`, и ни один `item.id` не совпадает с id любой транзакции user B

#### Scenario: Sorted DESC by created_at and paginated
- **GIVEN** 25 транзакций для user A с монотонным created_at
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions?page=2&per_page=10`
- **THEN** статус 200, `total == 25`, `page == 2`, `per_page == 10`, `len(items) == 10`, items отсортированы DESC по created_at, и slice покрывает DESC-ранг 11..20

#### Scenario: All four transaction types appear in response
- **GIVEN** для user A одна транзакция каждого типа (ACCRUAL, REDEMPTION, REVERSAL, ADMIN_ADJUSTMENT)
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions`
- **THEN** `{item["type"] for item in body["items"]}` SHALL content все 4 значения

#### Scenario: order_id=null for ADMIN_ADJUSTMENT row
- **GIVEN** для user A создана ADMIN_ADJUSTMENT транзакция с `order_id=NULL`
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions`
- **THEN** соответствующий item в теле ответа SHALL иметь `"order_id": null`

#### Scenario: Empty history
- **GIVEN** user A без loyalty_transactions
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions`
- **THEN** статус 200, `total == 0`, `items == []`

### Requirement: RBAC matrix registers the new loyalty prefix

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain two rows for CUSTOMER-only access:

- `("GET", "/api/v1/profile/loyalty")` → `{CUSTOMER}`.
- `("GET", "/api/v1/profile/loyalty/transactions")` → `{CUSTOMER}`.

Ни один маршрут SHALL NOT появиться в `PUBLIC_ROUTES`. Существующие строки матрицы НЕ изменяются.

В RED-change эти rows MUST NOT exist.

#### Scenario: RED — matrix rows absent
- **WHEN** тест проверяет `("GET", "/api/v1/profile/loyalty") in ROUTE_MATRIX`
- **THEN** assertion SHALL fail

#### Scenario: GREEN contract — balance route allows CUSTOMER only
- **GIVEN** GREEN завершён
- **WHEN** тест читает `ROUTE_MATRIX[("GET", "/api/v1/profile/loyalty")]`
- **THEN** value SHALL равняться `{CUSTOMER}`

#### Scenario: GREEN contract — transactions route allows CUSTOMER only
- **GIVEN** GREEN завершён
- **WHEN** тест читает `ROUTE_MATRIX[("GET", "/api/v1/profile/loyalty/transactions")]`
- **THEN** value SHALL равняться `{CUSTOMER}`

#### Scenario: Loyalty routes are not public
- **WHEN** тест читает `PUBLIC_ROUTES`
- **THEN** ни `("GET", "/api/v1/profile/loyalty")`, ни `("GET", "/api/v1/profile/loyalty/transactions")` SHALL NOT присутствовать

### Requirement: Existing profile routes are untouched

Существующие `GET /api/v1/profile` и `PATCH /api/v1/profile` SHALL оставаться в матрице с `{CUSTOMER}`. Новый prefix `/profile/loyalty` НЕ заменяет и не модифицирует их.

#### Scenario: Existing GET /profile row preserved
- **WHEN** тест читает `ROUTE_MATRIX[("GET", "/api/v1/profile")]`
- **THEN** value SHALL содержать `CUSTOMER`
