## ADDED Requirements

_References: PDD §3, §5.2, §5.4, §7.1 Phase 5 item 2, INV-002, INV-010, INV-013. GREEN фиксирует, что RED-контракт реализован._

### Requirement: Loyalty Pydantic schemas exist at `core_api.schemas.loyalty`

The module `core_api.schemas.loyalty` SHALL define three Pydantic v2 models:

- `LoyaltyBalanceResponse` with integer fields `balance` and `lifetime_accrued`.
- `LoyaltyTransactionResponse` (with `model_config = ConfigDict(from_attributes=True)`) exposing `id: UUID`, `type: LoyaltyTransactionType`, `amount: int`, `balance_after: int`, `order_id: UUID | None`, `description: str | None`, `created_at: datetime`.
- `LoyaltyTransactionListResponse` with fields `items: list[LoyaltyTransactionResponse]`, `page: int`, `per_page: int`, `total: int`.

#### Scenario: Module is importable after GREEN
- **WHEN** код выполняет `from core_api.schemas.loyalty import LoyaltyBalanceResponse, LoyaltyTransactionResponse, LoyaltyTransactionListResponse`
- **THEN** импорты SHALL завершиться без ошибки

### Requirement: `get_balance` service returns balance + accrual-only lifetime

The function `core_api.services.loyalty.get_balance(*, user_id, db_session) -> LoyaltyBalanceResponse` SHALL:

- SELECT `loyalty_accounts.balance` WHERE `user_id = :user_id`. Если row отсутствует — поднять `LoyaltyAccountMissingError`.
- Выполнить `SELECT COALESCE(SUM(amount), 0) FROM loyalty_transactions WHERE user_id = :user_id AND type = 'accrual'`.
- Вернуть `LoyaltyBalanceResponse(balance=<row.balance>, lifetime_accrued=<aggregate>)`.

#### Scenario: Balance returns accrual-only lifetime
- **GIVEN** user_a с `LoyaltyAccount(balance=500)` и ACCRUAL-транзакциями на 350
- **WHEN** вызван `get_balance(user_id=user_a.id, db_session=db)`
- **THEN** результат SHALL быть `LoyaltyBalanceResponse(balance=500, lifetime_accrued=350)`

#### Scenario: Missing account raises LoyaltyAccountMissingError
- **GIVEN** user_a существует, но loyalty_accounts row для него отсутствует
- **WHEN** вызван `get_balance(user_id=user_a.id, db_session=db)`
- **THEN** поднимается `LoyaltyAccountMissingError`

### Requirement: `list_transactions` service returns paginated DESC feed filtered by user_id

The function `core_api.services.loyalty.list_transactions(*, user_id, page, per_page, db_session) -> LoyaltyTransactionListResponse` SHALL:

- Подсчитать `total = SELECT COUNT(*) FROM loyalty_transactions WHERE user_id = :user_id`.
- Выбрать `SELECT * FROM loyalty_transactions WHERE user_id = :user_id ORDER BY created_at DESC OFFSET (page-1)*per_page LIMIT per_page`.
- Валидировать rows в `LoyaltyTransactionResponse.model_validate(...)`.
- Вернуть `LoyaltyTransactionListResponse(items=..., page=page, per_page=per_page, total=total)`.

#### Scenario: Returns DESC-sorted slice with correct total
- **GIVEN** 25 транзакций для user_a
- **WHEN** вызван `list_transactions(user_id=user_a.id, page=2, per_page=10, db_session=db)`
- **THEN** `total == 25`, `page == 2`, `per_page == 10`, `len(items) == 10`, items отсортированы created_at DESC, slice = DESC-ранг 11..20

#### Scenario: Cross-user isolation
- **GIVEN** user_a: 2 транзакции, user_b: 3 транзакции
- **WHEN** вызван `list_transactions(user_id=user_a.id, ...)`
- **THEN** `total == 2` AND все items принадлежат user_a

### Requirement: GET /api/v1/profile/loyalty returns balance to customer

The route `GET /api/v1/profile/loyalty` SHALL:

- Быть зарегистрирован в `core_api.routers.profile_loyalty` под prefix `/api/v1/profile/loyalty`.
- Использовать `get_current_user` dependency; RBAC middleware гарантирует только CUSTOMER (согласно ROUTE_MATRIX).
- Делегировать в `get_balance(user_id=current_user["user_id"], db_session=db)`.
- При `LoyaltyAccountMissingError` → `HTTPException(status_code=500)`.
- Возвращать JSON `{"balance": int, "lifetime_accrued": int}`.

#### Scenario: Customer receives balance and lifetime_accrued
- **GIVEN** user_a, balance=500, ACCRUAL-сумма=350; JWT с sub=user_a.id, role=customer
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty`
- **THEN** статус 200, тело `{"balance": 500, "lifetime_accrued": 350}`

### Requirement: GET /api/v1/profile/loyalty/transactions returns paginated own-user feed

The route `GET /api/v1/profile/loyalty/transactions` SHALL:

- Быть зарегистрирован в `core_api.routers.profile_loyalty`.
- Принимать `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=100)`.
- Делегировать в `list_transactions(user_id=current_user["user_id"], page=..., per_page=..., db_session=db)`.
- Возвращать JSON с ключами `items`, `page`, `per_page`, `total`.

#### Scenario: Paginated + sorted + isolated
- **GIVEN** user_a (25 транзакций), JWT с sub=user_a.id
- **WHEN** клиент шлёт `GET /api/v1/profile/loyalty/transactions?page=2&per_page=10`
- **THEN** статус 200, `total == 25`, `page == 2`, `per_page == 10`, `len(items) == 10`

### Requirement: RBAC matrix rows for loyalty routes

`core_api.rbac_matrix.ROUTE_MATRIX` SHALL contain two CUSTOMER-only rows:

- `("GET", "/api/v1/profile/loyalty")` → `{CUSTOMER}`.
- `("GET", "/api/v1/profile/loyalty/transactions")` → `{CUSTOMER}`.

#### Scenario: Both routes are CUSTOMER-only
- **WHEN** тест читает ROUTE_MATRIX
- **THEN** оба ключа присутствуют, value каждого равно `{CUSTOMER}`
