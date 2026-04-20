## Context

Personal-area surface для баллов лояльности. Customer UI (Phase 5) нуждается в двух read-only API: текущий баланс и пагинированная история начислений/списаний. Мутационная часть уже существует (checkout — ACCRUAL/REDEMPTION, order_cancel — REVERSAL) и здесь не трогается.

Текущее состояние:
- `loyalty_accounts(user_id PK, balance, created_at)` — row создаётся при ACTIVE-регистрации в Phase 1 (`services/user.activate`).
- `loyalty_transactions(id, user_id, order_id NULLABLE, type, amount, balance_after, description, created_at)` с композитным индексом `(user_id, created_at DESC)` из PDD §5.4.
- `shared.enums.LoyaltyTransactionType`: `ACCRUAL`, `REDEMPTION`, `REVERSAL`, `RESERVATION`, `ADMIN_ADJUSTMENT`.
- Существующий `routers/profile.py` обслуживает `/api/v1/profile` и `/api/v1/profile` PATCH. Delivery addresses уже живут в собственном prefix `/api/v1/profile/addresses`. Мы следуем тому же паттерну.

Аналог по стилю: `routers/admin_orders.py` + `services/order_history.py` (admin-orders-api) — staff-scoped read-only surface с RBAC-матрицей и отдельным сервисом. Этот change делает customer-scoped симметрично.

## Goals / Non-Goals

**Goals:**
- Зафиксировать в RED контракт: два customer-only endpoint-а, сервисный модуль с двумя функциями, три Pydantic-схемы, две строки RBAC-матрицы.
- Ввести failing-тесты, которые покрывают: happy-path, zero-balance, все 4 типа транзакций, пагинацию, DESC-сортировку, cross-user isolation (INV-010), 401 без токена, 403 для не-CUSTOMER ролей, 422 для per_page > 100, data-integrity ошибку при отсутствии loyalty_accounts row.
- Дать GREEN-фазе однозначный чек-лист "что реализовывать".

**Non-Goals:**
- Реализация — GREEN.
- Мутационные endpoint-ы (redeem, accrue, admin_adjustment).
- Расширение существующего `/api/v1/profile` ответа баллансом — отдельный prefix лучше изолирует concerns.
- Денормализация `lifetime_accrued` в колонку loyalty_accounts.
- Дополнительные фильтры в transactions (по type/дате) — MVP не требует.

## Decisions

**D1 — отдельный prefix `/api/v1/profile/loyalty` вместо расширения `/api/v1/profile`.**
Rationale: loyalty — отдельный concern; паттерн уже отработан на delivery_addresses (`/api/v1/profile/addresses`). Клиентский UI запрашивает balance асинхронно от профиля и ре-fetch-ит при изменениях (после checkout, после admin_adjustment уведомления). Альтернатива — вложить `balance` в `GET /api/v1/profile` — смешивает read/write concerns и заставляет invalidate profile-кэш при каждом изменении баллов.

**D2 — `lifetime_accrued` вычисляется on-the-fly агрегатом `SUM(amount) WHERE type='accrual'`, а не денормализуется.**
Rationale: индекс `(user_id, created_at DESC)` уже даёт быстрый scan партиции пользователя; у реального пользователя число транзакций на год — десятки, не миллионы. Денормализация добавила бы третье место обновления в checkout/cancel (сейчас: balance + transaction row → стало бы +lifetime_accrued_column). Это бьёт INV-004 (атомарность) и увеличивает поверхность рассинхронизации. REVERSAL и REDEMPTION сознательно не трогают lifetime — это метрика "всего заработано" (= customer "level" в терминах продуктовых метрик), не "всего доступно".

**D3 — сервис фильтрует по user_id в WHERE; API-handler пересылает туда user_id из JWT.**
Rationale: INV-002/INV-010 defence-in-depth. Если handler забудет передать user_id — сервис упадёт (keyword-only arg). Если забудет сервис — утечка. Сервис не доверяет handler-у, это стандарт проекта (см. `list_orders(user_id=...)`).

**D4 — `LoyaltyAccountMissingError` → HTTP 500, не 404.**
Rationale: отсутствие loyalty_accounts row для ACTIVE user — data-integrity issue (нарушение инварианта из Phase 1, строка обязана быть создана). 404 дал бы клиенту ощущение "у меня нет аккаунта лояльности", 500 корректно сигнализирует incident для мониторинга.

**D5 — реиспользуем `LoyaltyTransactionType` напрямую как тип `type` в Pydantic.**
Rationale: Pydantic v2 умеет сериализовать enum в str по значению. Тесты проверяют строковые значения (`"accrual"`, `"redemption"`, …), которые совпадают с `LoyaltyTransactionType` values. Альтернатива — Literal-тип — дублирование enum.

**D6 — модель router-а копирует паттерн `admin_orders.py`: `router = APIRouter(prefix="/api/v1/profile/loyalty", tags=["loyalty"])` + два handler-а.**
Rationale: единообразие, минимум surprises.

**D7 — тесты используют существующие фикстуры `db_session` (PG), `admin_headers/barista_headers/courier_headers` (random-sub JWT) и `auth_headers_for_user()` из `tests/_helpers/jwt.py` (детерминированный sub). Первая группа покрывает RBAC 403; вторая — per-user isolation. Rationale: patterns уже проверены в admin-orders/courier/order-history тестах.

## Risks / Trade-offs

- [Risk] Агрегат `SUM(amount) WHERE type='accrual'` ведёт второй SQL-запрос помимо SELECT balance → Mitigation: два query против одного row/одного PK — миллисекунды; индекс `(user_id, created_at DESC)` хотя и не совсем идеален для SUM-по-type, работает через Index Scan по user_id. Если понадобится — добавим partial index `(user_id) WHERE type='accrual'` в будущем. Документируем в spec.
- [Risk] `lifetime_accrued` расходится с ручным подсчётом "total earned" в бизнес-интерпретации → Mitigation: в задании явно прописано: "REVERSAL в lifetime не влияет". Тесты явно сеют REVERSAL/REDEMPTION и проверяют, что они не входят в lifetime.
- [Risk] Cross-user data leak при ошибке в handler-е → Mitigation: тест `test_user_A_cannot_see_user_B_transactions` проверяет именно такое — сервис фильтрует в WHERE, handler только передаёт.
- [Trade-off] Отдельный prefix требует вторую RBAC-строку, vs. одна строка при расширении `/profile` → явные строки — единственный источник истины (ROUTE_MATRIX), лучше, чем неявное наследование.

## Migration Plan

RED-change не создаёт миграций и не меняет код. Откат — `openspec archive` (логический drop change folder). GREEN-change также без миграций (индексы и таблицы уже существуют с Phase 1/3).
