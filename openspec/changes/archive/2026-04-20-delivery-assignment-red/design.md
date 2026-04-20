## Context

Phase 3 (§6.1 Order Lifecycle, §7.6 Cancellation Chain) уже в main: миграция `0005_phase3_schema.py`, модели `Order`, `Payment`, `LoyaltyAccount` и сервисы `order_lifecycle.transition_order` / `order_cancel.cancel_order`. Phase 4 (Delivery) требует ЕЩЁ один параллельный конечный автомат: Delivery Assignment Lifecycle (PDD §6.3) — курьерский трек для заказов `type=DELIVERY`, с состояниями `AWAITING_COURIER → COURIER_ASSIGNED → PICKED_UP → DELIVERED` и отменой до взятия.

Нулевой runtime-код под §6.3 пока отсутствует: нет enum-а, модели, миграции, сервиса, роутера, RBAC-строк. Order Lifecycle *умеет* переходить `READY→IN_DELIVERY` и `IN_DELIVERY→COMPLETED`, но на эти переходы нет рычагов: админ/бариста/курьер физически не могут инициировать их через тот контракт, который зафиксирован §6.3 (курьер берёт → забирает → доставляет, bridge в Order Lifecycle).

Этот RED-change добавляет ТОЛЬКО failing-тесты, фиксирующие контракт: state machine, optimistic lock, bridge к §6.1, RBAC по INV-010, атомарность по INV-004. Продакшен-код прибивается в `delivery-assignment-green`.

**Affected modules:** **[core-api]** (сервис + роутер + тесты), **[shared]** (будущий enum + модель — объявлены в тестах как import paths, не реализованы), **[database]** (будущая миграция 0007 — объявлена как import path в тестах через `migrated_db_session`). Никаких [payment-worker] / [sms-worker] / [web-*] / [redis].

Авторитативные ссылки: PDD §6.3 (Delivery Assignment Lifecycle), §6.1 (Order Lifecycle — для bridge на READY→IN_DELIVERY и IN_DELIVERY→COMPLETED), INV-010, INV-016, INV-004.

## Goals / Non-Goals

**Goals:**
- RED-сьют MUST падать на HEAD: ни `shared.enums.DeliveryAssignmentStatus`, ни `shared.models.delivery_assignment.DeliveryAssignment`, ни `core_api.services.delivery_assignment`, ни `core_api.routers.courier`, ни `core_api.services.order_lifecycle.transition_order_bridge` не существуют.
- Зафиксировать все переходы §6.3 как allow-list: `(AWAITING_COURIER→COURIER_ASSIGNED)`, `(COURIER_ASSIGNED→PICKED_UP)`, `(PICKED_UP→DELIVERED)`, `(AWAITING_COURIER→CANCELLED)`, `(COURIER_ASSIGNED→CANCELLED)`. Всё остальное — `AssignmentTransitionError(reason="forbidden_transition")`.
- Зафиксировать bridge §6.3 → §6.1 в одной DB-транзакции: `pickup_assignment` MUST изменить `assignment.status=PICKED_UP` И `order.status=IN_DELIVERY` в одном commit’е; `deliver_assignment` — `assignment.status=DELIVERED` + `order.status=COMPLETED` + `_accrue_loyalty` (INV-003).
- Зафиксировать хук `PAID→PREPARING`: при `order.type == DELIVERY` в той же txn вставляется `DeliveryAssignment(status=AWAITING_COURIER)`. Для `PICKUP` — хук не срабатывает. UNIQUE-constraint на `order_id` гарантирует идемпотентность на уровне БД.
- Зафиксировать optimistic lock: `UPDATE ... WHERE status='AWAITING_COURIER' RETURNING id`; 0 строк ⇒ `AssignmentAlreadyTakenError`. Тест имитирует гонку через две сессии.
- Зафиксировать RBAC INV-010: все 5 courier-маршрутов ТОЛЬКО для COURIER; customer/barista/admin → 403.
- Зафиксировать cancel-bridge: `cancel_assignment_for_order` вызывается из `order_cancel.cancel_order` при админском cancel; переводит assignment в CANCELLED если он `AWAITING_COURIER` или `COURIER_ASSIGNED`; PICKED_UP — no-op (§6.3 запрещает).

**Non-Goals:**
- Любой продакшен-код (модель, миграция, сервис, роутер, изменения rbac/main) — ВСЁ в GREEN.
- Любые изменения в `order_lifecycle.transition_order` / `order_cancel.cancel_order` — GREEN.
- Push-уведомление курьеру при новом AWAITING_COURIER.
- Расчёт маршрута / ETA / геокоординаты.
- Аудит-лог смены курьера.
- Frontend курьерской панели.

## Decisions

### D1 — Сервисный слой: плоские функции, не класс

Как и `order_lifecycle` / `order_cancel`, `delivery_assignment` — модуль с функциями:

```python
list_available_for_courier(db: Session) -> list[AssignmentView]
take_assignment(assignment_id: UUID, courier_id: UUID, db: Session) -> DeliveryAssignment
pickup_assignment(assignment_id: UUID, courier_id: UUID, db: Session) -> DeliveryAssignment
deliver_assignment(assignment_id: UUID, courier_id: UUID, db: Session) -> DeliveryAssignment
cancel_assignment_for_order(order_id: UUID, db: Session) -> DeliveryAssignment | None
```

Rationale: тот же стиль, что и соседние сервисы. Тесты патчат функции как модуль-атрибуты. Класс-обёртка не нужна (нет состояния кроме session).

**Alternative rejected:** класс `DeliveryAssignmentService` — требует instance в каждом тесте, увеличивает mock-поверхность, ломает консистентность с другими service-модулями.

### D2 — Доменные ошибки: два типа

- `AssignmentTransitionError(reason: str)` — общий класс бизнес-ошибок. `reason`: `"assignment_not_found"`, `"forbidden_transition"`, `"not_owner"`, `"order_not_ready"`.
- `AssignmentAlreadyTakenError(AssignmentTransitionError)` — подкласс для optimistic-lock гонки (HTTP 409 отдельно). Наследование от `AssignmentTransitionError` гарантирует, что `except AssignmentTransitionError:` ловит и его — удобно в роутере. `reason="already_taken"`.

Роутер транслирует `reason` в HTTP:
- `assignment_not_found` → 404
- `already_taken` → 409
- `not_owner` → 403 (роль COURIER есть, но это чужой assignment)
- `order_not_ready`, `forbidden_transition` → 409

**Alternative rejected:** один общий exception и switch по `reason` — не отличить 403/409/404.

### D3 — Allow-list переходов как python-константа

```python
_ALLOWED_TRANSITIONS: set[tuple[DeliveryAssignmentStatus, DeliveryAssignmentStatus]] = {
    (AWAITING_COURIER, COURIER_ASSIGNED),
    (COURIER_ASSIGNED, PICKED_UP),
    (PICKED_UP, DELIVERED),
    (AWAITING_COURIER, CANCELLED),
    (COURIER_ASSIGNED, CANCELLED),
}
```

Всё, что не в множестве → `forbidden_transition`. RED-тест параметризованно перебирает декартово произведение `(src, dst)` минус allow-list и требует исключения. Это тот же стиль, что в `test_order_lifecycle.test_forbidden_transitions_raise`.

**Alternative rejected:** hardcode if-else ветки — взрывает цикломатическую сложность, плохо покрывается INV-016.

### D4 — Bridge к Order Lifecycle: новая `transition_order_bridge` без commit

Сейчас `transition_order` делает `db_session.commit()` в конце. Это нужно для HTTP-эндпоинтов (каждый вызов — одна транзакция). Но для bridge-вызова из `pickup_assignment` нужно:
- ту же сессию;
- изменить и assignment, и order;
- commit'нуть один раз (атомарно).

Решение: **вытянуть общее ядро** `_apply_transition(order_id, new_status, actor_role, db) -> Order` (без commit) и сделать две обёртки:

- `transition_order(order_id, new_status, actor_role, db_session) -> Order` — старая публичная функция, в конце делает `db_session.commit()`. Существующие тесты `test_order_lifecycle.py` продолжают проходить.
- `transition_order_bridge(order_id, new_status, actor_role, db_session) -> Order` — то же ядро, но БЕЗ commit’а. Используется изнутри `pickup_assignment` / `deliver_assignment`.

В `pickup_assignment`:
```python
assignment = _get_or_404(...)
_check_owner(assignment, courier_id)
_check_allowed(assignment.status, PICKED_UP)
if order.status != OrderStatus.READY:
    raise AssignmentTransitionError("order_not_ready")
assignment.status = PICKED_UP
assignment.picked_up_at = now()
transition_order_bridge(order.id, IN_DELIVERY, "courier", db)
db.commit()
```

RED-тест проверяет: после `pickup_assignment` `order.status == IN_DELIVERY` и `assignment.status == PICKED_UP` — обе в одной сессии. Тест на откат: если `transition_order_bridge` бросит — и assignment не сохранится (тест патчит bridge чтобы `raise RuntimeError` и проверяет rollback обеих сущностей).

**Alternative rejected:** передавать флаг `commit: bool = True` в одну функцию — менее явно, легко забыть в HTTP-вызывающей стороне.

### D5 — Partial index в миграции 0007

Для быстрого feed'а курьера (`GET /courier/assignments/available`) — partial index:

```sql
CREATE INDEX ix_delivery_assignments_awaiting ON delivery_assignments (status)
WHERE status = 'AWAITING_COURIER';
```

RED-тестов на это НЕТ (это тест GREEN-миграции, не контракта сервиса). Но фиксируем в design.md как обязательство для GREEN.

### D6 — Хук в `transition_order` на `PAID→PREPARING`

Встраивается ВНУТРИ ядра `_apply_transition` (не в обёртке), чтобы и `transition_order`, и `transition_order_bridge` имели один side-effect. Проверка:

```python
if key == (PAID, PREPARING) and order.type == OrderType.DELIVERY:
    db.add(DeliveryAssignment(order_id=order.id, status=AWAITING_COURIER))
    db.flush()   # UNIQUE(order_id) уже защитит от дублей
```

RED-тест сидирует `Order(type=DELIVERY, status=PAID)`, зовёт `transition_order(..., PREPARING, "barista", db)`, проверяет наличие ровно одной `DeliveryAssignment` с `status=AWAITING_COURIER` и `order_id=order.id`. Для `Order(type=PICKUP, status=PAID)` — никакой записи.

Идемпотентность: UNIQUE на `order_id` гарантирует, что повторный вставка из той же или другой транзакции упадёт `IntegrityError`. В GREEN это будет contract, но в тестах второй вызов `transition_order(PAID→PREPARING)` на том же заказе и так невозможен: allow-list запрещает `PREPARING→PREPARING`.

### D7 — Cancel-bridge из order_cancel

`order_cancel.cancel_order` сейчас работает на 5 шагах, из них только шаг 4 (обновление `order.status=CANCELLED`) касается §6.1. Для §6.3 надо ДО commit’а: попытаться отменить assignment (если такой есть и он не PICKED_UP). GREEN добавит шаг 4-бис. RED фиксирует контракт `cancel_assignment_for_order(order_id, db) -> DeliveryAssignment | None`:
- нет assignment → None;
- assignment в AWAITING_COURIER / COURIER_ASSIGNED → перевод в CANCELLED + `cancelled_at=now()` + возврат объекта;
- assignment в PICKED_UP → None (no-op, не трогаем — §6.3 запрещает);
- assignment в DELIVERED / CANCELLED → None (уже терминальное, no-op).

RED-тест зовёт `cancel_assignment_for_order` напрямую для каждого стартового статуса и проверяет результат.

### D8 — Optimistic lock: SQL UPDATE ... RETURNING

`take_assignment`:
```python
row_count = db.execute(
    update(DeliveryAssignment)
    .where(DeliveryAssignment.id == aid, DeliveryAssignment.status == AWAITING_COURIER)
    .values(status=COURIER_ASSIGNED, courier_id=cid, assigned_at=now())
    .returning(DeliveryAssignment.id)
).scalar_one_or_none()
if row_count is None:
    raise AssignmentAlreadyTakenError()
```

RED-тест использует две сессии (фикстура `migrated_db_session` + отдельная сессия на тот же engine). Первая сессия коммитит `take_assignment(aid, c1)`; вторая сессия зовёт `take_assignment(aid, c2)` и получает `AssignmentAlreadyTakenError`. На выходе в БД `courier_id=c1`, `status=COURIER_ASSIGNED`.

### D9 — RBAC для courier-маршрутов

Добавляются в `rbac_matrix.py` GREEN-циклом:
```python
("GET",  "/api/v1/courier/assignments/available"): {COURIER},
("GET",  "/api/v1/courier/assignments/mine"):       {COURIER},
("POST", "/api/v1/courier/assignments/{assignment_id}/take"):    {COURIER},
("POST", "/api/v1/courier/assignments/{assignment_id}/pickup"):  {COURIER},
("POST", "/api/v1/courier/assignments/{assignment_id}/deliver"): {COURIER},
```

RED-тест: для каждого маршрута + каждого из `customer_headers` / `barista_headers` / `admin_headers` → 403. Админ — тоже 403: курьерские ручки строго изолированы (администрирование assignment-ами — отдельная фича с админским префиксом, вне scope).

### D10 — Тестовый layout и фикстуры

Используем те же фикстуры, что уже есть в `conftest.py`: `db` (SQLite на StaticPool, метаданные создаются из `Base.metadata`), `courier_headers` / `barista_headers` / `customer_headers` / `admin_headers` / `client`. Для optimistic-lock-теста используется `migrated_db_session` (PostgreSQL) или две отдельные sqlite-сессии на тот же engine.

Import целевых модулей — ВНУТРИ тестов (как в существующих RED-тестах), чтобы сбор файла не падал до того, как GREEN создаст модули.

## Risks / Trade-offs

- **[Risk]** SQLite vs PostgreSQL enum: SQLite не знает native enum → хранит как TEXT. `DeliveryAssignmentStatus` как SQLAlchemy `Enum(values_callable=...)` уже работает в соседних моделях (`Order`). → **Mitigation:** тот же паттерн, что в `Order.status`.
- **[Risk]** Partial index не создаётся на sqlite → тесты, использующие SQLite-фикстуру, не проверят его. → **Mitigation:** проверка индекса — отдельный migration-тест на `migrated_db_session` в GREEN. RED не проверяет индекс.
- **[Risk]** Optimistic-lock тест через две сессии на in-memory SQLite StaticPool не работает (одна и та же соединение-сессия). → **Mitigation:** optimistic-lock тест написан так, что SKIP-ается на SQLite (`pytest.skip(...)` при `_TEST_DB_URL.startswith("sqlite")`). На PostgreSQL он боевой.
- **[Risk]** Рефакторинг `transition_order` на `_apply_transition` ломает существующие RED-тесты из `test_order_lifecycle.py`. → **Mitigation:** публичный контракт (`transition_order(order_id, new_status, actor_role, db_session) -> Order`) сохраняется 1-в-1; меняется только внутренняя организация. GREEN-цикл VERIFY-шаг гонит `pytest services/core-api/tests/test_order_lifecycle.py` целиком и требует зелёного.
- **[Risk]** Bridge через одну сессию: если `pickup_assignment` пометит assignment, но `transition_order_bridge` упадёт — без commit rollback сессии вернёт всё. → **Mitigation:** тест патчит bridge на `raise RuntimeError`, ожидает, что после исключения в отдельной сессии `order.status` и `assignment.status` без изменений (нулевой коммит).

## Atomicity Analysis (INV-004)

Bridge-операции (`pickup_assignment`, `deliver_assignment`) МОГУТ трогать две таблицы + ledger:

1. `delivery_assignments.status` / `picked_up_at` / `delivered_at` — UPDATE.
2. `orders.status` — UPDATE (через `_apply_transition`).
3. `loyalty_transactions` INSERT + `loyalty_accounts.balance` UPDATE — ТОЛЬКО для `deliver_assignment` (COMPLETED).

Все три должны коммититься ОДНОЙ транзакцией. Гарантируется схемой D4: `pickup_assignment` / `deliver_assignment` работают только с одной переданной `Session`, вызывают `transition_order_bridge` (flush без commit), и в самом конце своего тела делают `db.commit()`. При любом исключении между шагами FastAPI-зависимость `get_session` откатывает сессию (в тестах — фикстура `db` сделает `rollback()` на выходе).

RED-тесты фиксируют контракт атомарности:
- `test_pickup_rolls_back_if_order_transition_fails`: патч `transition_order_bridge` на `raise RuntimeError("boom")`; после raise — assignment БЕЗ изменений, order БЕЗ изменений.
- `test_deliver_rolls_back_if_loyalty_fails`: патч `_accrue_loyalty` на `raise RuntimeError("boom")`; assignment не `DELIVERED`, order не `COMPLETED`, no-ledger-row.

Финансовый эффект (loyalty accrual): сами баллы начисляются через `_accrue_loyalty` внутри `_apply_transition(..., COMPLETED)`, т.е. в одной транзакции с `order.status=COMPLETED` и `assignment.status=DELIVERED`. Это INV-004.

## State Machine Reference (INV-016)

PDD §6.3 transitions (исчерпывающий allow-list):

| From | To | Trigger (service function) | Roles | Extra precondition |
|------|----|-------|-------|--------------------|
| AWAITING_COURIER | COURIER_ASSIGNED | `take_assignment` | COURIER | optimistic lock; assignment ещё AWAITING_COURIER |
| COURIER_ASSIGNED | PICKED_UP | `pickup_assignment` | COURIER (ownership) | `order.status == READY`; bridge → order IN_DELIVERY |
| PICKED_UP | DELIVERED | `deliver_assignment` | COURIER (ownership) | bridge → order COMPLETED + accrual (INV-003) |
| AWAITING_COURIER | CANCELLED | `cancel_assignment_for_order` | ADMIN (через order_cancel) | `order.status` переходит в CANCELLED |
| COURIER_ASSIGNED | CANCELLED | `cancel_assignment_for_order` | ADMIN (через order_cancel) | `order.status` переходит в CANCELLED |

Переходы НЕ в allow-list (MUST raise `forbidden_transition`):
- `DELIVERED → *` (терминальное)
- `CANCELLED → *` (терминальное)
- `COURIER_ASSIGNED → AWAITING_COURIER` (курьер не отказывается, §6.3)
- `PICKED_UP → COURIER_ASSIGNED` (нельзя откатить забор)
- `PICKED_UP → CANCELLED` (§6.3 запрещает явно)
- `AWAITING_COURIER → PICKED_UP` / `AWAITING_COURIER → DELIVERED` / прочие «прыжки через ступень»
- `COURIER_ASSIGNED → DELIVERED` (требуется PICKED_UP)

## Migration Plan

**RED change:** миграции НЕ создаются. Rollback — `git revert`.

**GREEN change (для справки):**
- Forward-only миграция `0007_delivery_assignments.py`.
- Создаёт enum `delivery_assignment_status`, таблицу `delivery_assignments`, UNIQUE на `order_id`, partial index `ix_delivery_assignments_awaiting`.
- Backfill: для всех существующих orders со `status IN ('preparing','ready','in_delivery','completed')` и `type=DELIVERY` — вставить `DeliveryAssignment(status=AWAITING_COURIER)` (best-effort, курьер сам перепривяжется). Для новых MVP-инсталляций бекфилл пустой.
- Rollback: drop table + drop enum. Тест downgrade() в VERIFY-шаге GREEN.

## Open Questions

1. **Должна ли модель `DeliveryAssignment` хранить PII курьера или только FK на `staff_accounts`?**
   → Решение: только FK `courier_id → staff_accounts.id`. PII сотрудника уже изолирована в `staff_accounts` / `user_profile` (у курьера нет отдельного `user_profile`, но INV-013 всё равно соблюдается — в `DeliveryAssignment` НЕТ имени/телефона).

2. **Нужен ли `assignment_not_found` как 404 или 403 (чтобы не утекал факт существования)?**
   → Решение: 404. Для курьера «тот, кто может знать id» — это уже COURIER-токен. Информационная утечка минимальна; 404 понятнее.

3. **`cancel_assignment_for_order` вызывать ДО или ПОСЛЕ `send_order_notification` в `order_cancel.cancel_order`?**
   → Решение: ДО уведомления. Assignment — часть доменного состояния; уведомление — внешний side effect. Порядок: rights → promo → points → **assignment-cancel** → order.status=CANCELLED → notify → send_task(refund) → commit. GREEN зафиксирует.

4. **Нужен ли `picked_up_at` / `delivered_at` timestamp как часть бизнес-контракта?**
   → Решение: да. Это уже в ТЗ (см. user prompt). Тесты проверяют, что оба таймстампа заполняются при соответствующем переходе.
