## Why

Клиенту в личном кабинете (Phase 5) нужно видеть текущий баланс баллов и историю начислений/списаний (PDD §7.1 Phase 5 item 2, §5.2 Лояльность). Мутационные транзакции уже реализованы в Phase 3 (checkout / cancel / lifecycle), но read-only surface — balance и transaction feed — отсутствует. Без него customer UI лояльности построить невозможно.

Это RED-фаза двухшаговой модели — failing tests фиксируют контракт API, сервиса и RBAC до любой имплементации.

MVP phase: **Phase 5 — Loyalty & Promocodes** (PDD §7.1 item 2).

## What Changes

- Ввести failing-тесты для нового staff-isolated customer-read surface:
  - `GET /api/v1/profile/loyalty` → `LoyaltyBalanceResponse` (balance + lifetime_accrued).
  - `GET /api/v1/profile/loyalty/transactions` → `LoyaltyTransactionListResponse` (paginated, DESC по created_at).
- Ввести failing-тесты для нового сервисного модуля `core_api.services.loyalty`:
  - `get_balance(*, user_id, db_session)` — SELECT `loyalty_accounts.balance` + агрегат `SUM(amount) WHERE type='accrual'` для `lifetime_accrued`; отсутствие row → domain error (500 на API).
  - `list_transactions(*, user_id, page, per_page, db_session)` — пагинированный feed, строго фильтрованный по `user_id` (INV-002, INV-010), ORDER BY `created_at DESC`.
- Ввести failing-тесты для новых Pydantic-схем `core_api.schemas.loyalty` (`LoyaltyBalanceResponse`, `LoyaltyTransactionResponse`, `LoyaltyTransactionListResponse`) с полями из задания.
- Ввести failing-тесты для `rbac_matrix`:
  - `("GET", "/api/v1/profile/loyalty")` → `{CUSTOMER}`.
  - `("GET", "/api/v1/profile/loyalty/transactions")` → `{CUSTOMER}`.
  - Маршруты НЕ в `PUBLIC_ROUTES`; admin/barista/courier → 403; missing token → 401.
- Ввести isolation-тест: запрос `/transactions` с JWT user A после посева транзакций user A + user B возвращает ТОЛЬКО транзакции user A (INV-010).
- Ни сервис, ни router, ни schema, ни `main.py`-wiring, ни rbac-строки в этой change не появляются. Все тесты обязаны упасть (ImportError / KeyError / 403 / assertion).

## Capabilities

### New Capabilities
- `customer-loyalty-api`: Customer-scoped read-only surface для баллов лояльности — текущий баланс + lifetime_accrued + пагинированная история транзакций.

### Modified Capabilities
<!-- Нет — RED вводит только новые failing-тесты для новой capability. -->

## Non-Goals

- Реализация сервиса, схем, router-а, rbac-строк и регистрации в `main.py` (GREEN-фаза).
- Мутационные endpoint-ы (`POST /redeem`, `POST /accrue`, admin_adjustment UI) — остаются внутри checkout/cancel pipeline (Phase 3) и Phase 6 users management.
- Расширение существующего `GET /api/v1/profile` — отдельный prefix `/profile/loyalty` намеренно.
- Новые миграции / индексы — `loyalty_transactions(user_id, created_at DESC)` уже существует (PDD §5.4).
- Конвертация баллов в копейки / деньги — баллы остаются штуками на API-boundary (1 балл = 1₽ только в UI).
- Frontend (customer loyalty UI лежит в отдельной web-customer change).
- Денормализация `lifetime_accrued` — считается on-the-fly агрегатом.

## Impact

- **Code**: добавляет три новых тестовых модуля `services/core-api/tests/test_profile_loyalty_balance.py`, `test_profile_loyalty_transactions.py`, `test_profile_loyalty_rbac.py`. Может потребоваться небольшой helper-фабрика `make_loyalty_account` / `seed_loyalty_transactions` в `tests/_factories/` для сборки row-ов LoyaltyAccount и LoyaltyTransaction.
- **APIs**: фиксирует контракт `GET /api/v1/profile/loyalty` и `GET /api/v1/profile/loyalty/transactions` (без реализации).
- **Dependencies**: переиспользует `shared.models.loyalty_account.LoyaltyAccount`, `shared.models.loyalty_transaction.LoyaltyTransaction`, `shared.enums.LoyaltyTransactionType`. Ни одного нового пакета.
- **Inviolable rules touched**: INV-002 (серверная авторизация), INV-010 (изоляция ролей — только CUSTOMER), INV-013 (PII: user_id — opaque UUID в JWT-sub).
- **Systems**: PostgreSQL (read-only SELECT / aggregate по `loyalty_accounts` и `loyalty_transactions` с существующим композитным индексом). Ни Redis, ни миграций, ни Celery.
