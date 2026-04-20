## Context

RED-фаза создала 28 failing-тестов, покрывающих сервис, схемы, router и RBAC. GREEN реализует минимум, чтобы все тесты стали зелёными — без перепроектирования.

Существующие соседи, стиль которых мы копируем:
- `routers/order_history.py` — `_get_session` обёртка, `get_current_user` dep, `Query(..., ge, le)` для пагинации.
- `routers/admin_orders.py` — конвенция `HTTPException(404)` из domain error.
- `services/order_history.py::list_orders` — pattern `total = count(); rows = select(...).offset().limit()`.
- `schemas/order_history.py::OrderListResponse` — pattern paginated body.

## Goals / Non-Goals

**Goals:**
- Реализовать три Pydantic-схемы, сервис с двумя функциями и исключением, router с двумя endpoints, добавить две строки RBAC.
- Все 28 RED-тестов → PASS.
- Zero regression в уже зелёных наборах (`test_route_coverage`, `test_profile_endpoints`, `test_admin_orders_*`).

**Non-Goals:**
- Рефакторинг соседних сервисов.
- Альтернативные ORM-запросы (windowed aggregate + транзакции одним запросом) — два SQL это OK.
- Изменение существующих схем или роутеров.

## Decisions

**D1 — Схема `LoyaltyTransactionResponse` использует `type: LoyaltyTransactionType`, не `str`.**
Pydantic v2 сериализует enum по значению автоматически. Тест `test_transactions_body_contains_all_four_types` ожидает строковые values (`"accrual"`, …) — они совпадают с enum values. Альтернатива `Literal[...]` — лишний дубликат enum.

**D2 — `LoyaltyTransactionResponse.model_config = ConfigDict(from_attributes=True)`.**
Нужно чтобы `[LoyaltyTransactionResponse.model_validate(row) for row in rows]` работало прямо из ORM-объектов LoyaltyTransaction.

**D3 — `get_balance` делает два запроса: `SELECT balance` и `SELECT SUM(amount) WHERE type='accrual'`.**
Альтернатива — один запрос с CTE/FULL JOIN — усложнит код без выигрыша. Оба запроса bounded по user_id (индекс PK на loyalty_accounts, (user_id, created_at DESC) на loyalty_transactions). `COALESCE(SUM(amount), 0)` гарантирует int вместо None.

**D4 — `LoyaltyAccountMissingError` на отсутствующий row.**
Вызывается только тогда, когда `db_session.get(LoyaltyAccount, user_id)` вернул None. В router → `HTTPException(status_code=500, detail="loyalty_account_missing")`.

**D5 — Router читает `user_id` из `get_current_user` dependency (используется в `profile.py`, `order_history.py`).**
Это стандарт проекта. `current_user["user_id"]` — UUID.

**D6 — Handler прокидывает `user_id` в сервис, сервис повторно фильтрует WHERE user_id = :user_id.**
Defence-in-depth (INV-002/INV-010). Если handler пропустит user_id — сервис упадёт (keyword-only).

**D7 — Router-файл называется `profile_loyalty.py`, prefix `/api/v1/profile/loyalty`, tags `["loyalty"]`.**
Единообразие с `profile.py`, `delivery_addresses.py`.

## Risks / Trade-offs

- [Risk] SUM с `type='accrual'` требует Index Scan по `(user_id, created_at DESC)` с filter по type → Mitigation: у реального customer-а десятки accrual-rows, cost не ощутим. Добавим partial index только если профайлер покажет bottleneck.
- [Risk] `from_attributes=True` на LoyaltyTransactionResponse даст SQLAlchemy column-access → ленивый load `order_id` — нет, это plain UUID column, не relationship, безопасно.
- [Trade-off] Два SQL-запроса в balance endpoint vs. один с UNION ALL — оба bounded, difference меньше network RTT.

## Migration Plan

Никаких миграций. Deploy — стандартный rolling. Откат — revert commit; контракт изолирован от остальной Phase 5.
