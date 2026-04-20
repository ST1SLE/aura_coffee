## Why

Phase 4 (Delivery) требует реализовать Delivery Assignment Lifecycle (PDD §6.3) — параллельный конечный автомат для курьерского трека заказа. Сейчас Order Lifecycle (§6.1) умеет переходить READY→IN_DELIVERY и IN_DELIVERY→COMPLETED, но нет ни записи `delivery_assignments`, ни механизма «взять заказ на себя» с optimistic lock (INV-010, INV-016). Без этого курьер не может физически получить заказ из бекенда, а админская отмена (§7.6) не знает о наличии связанного assignment. TDD-дисциплина требует зафиксировать все правила §6.3 (состояния, переходы, форbidden-пары, ролевая изоляция, optimistic lock, bridge в Order Lifecycle) как падающие тесты до того, как модель / сервис / роутер появятся.

## What Changes

- Добавить `services/core-api/tests/test_delivery_assignment_state_machine.py` — unit-тесты для `core_api.services.delivery_assignment`:
  - Все разрешённые переходы из §6.3: AWAITING_COURIER→COURIER_ASSIGNED (`take_assignment`), COURIER_ASSIGNED→PICKED_UP (`pickup_assignment`), PICKED_UP→DELIVERED (`deliver_assignment`), AWAITING_COURIER→CANCELLED и COURIER_ASSIGNED→CANCELLED (`cancel_assignment_for_order`).
  - Все запрещённые переходы (DELIVERED→*, CANCELLED→*, PICKED_UP→COURIER_ASSIGNED, PICKED_UP→CANCELLED, COURIER_ASSIGNED→AWAITING_COURIER) поднимают `AssignmentTransitionError(reason="forbidden_transition")` — INV-016.
  - `cancel_assignment_for_order` на PICKED_UP/DELIVERED не сбрасывает состояние и возвращает контролируемый no-op (assignment не трогается; заказ уже у курьера).
  - Ownership-check: `pickup_assignment` / `deliver_assignment` вызванные не-владельцем → `AssignmentTransitionError(reason="not_owner")` (INV-010).
  - Precondition: `pickup_assignment` требует `order.status == READY` → иначе `AssignmentTransitionError(reason="order_not_ready")`.
- Добавить `services/core-api/tests/test_delivery_assignment_bridge.py` — интеграционные тесты сцепки двух state machine в одной DB-транзакции:
  - `PAID→PREPARING` хук в `transition_order`: при `order.type == DELIVERY` в той же txn создаётся `DeliveryAssignment(status=AWAITING_COURIER)`. Для `PICKUP` — не создаётся. Идемпотентно: повторный вызов хука (за счёт UNIQUE `order_id`) не поднимает исключение на бизнес-уровне — повторно хук не вызывается, тест фиксирует наличие ровно одной записи после счастливого пути.
  - `pickup_assignment` поднимает `assignment.status=PICKED_UP` И в ТОЙ ЖЕ txn переводит `order.status: READY→IN_DELIVERY` (через новую `transition_order_bridge` — flush без commit). Атомарность: при искусственном исключении после flush-а сессии rollback возвращает обе сущности в исходное состояние.
  - `deliver_assignment` поднимает `assignment.status=DELIVERED` И `order.status: IN_DELIVERY→COMPLETED`, вызывает `_accrue_loyalty` (тест проверяет ACCRUAL-запись с суммы товаров без delivery_fee — INV-003).
  - `cancel_assignment_for_order` вызывается из `order_cancel.cancel_order` при админской отмене: AWAITING_COURIER → CANCELLED, COURIER_ASSIGNED → CANCELLED; PICKED_UP — no-op (согласно §6.3).
- Добавить `services/core-api/tests/test_courier_endpoints.py` — HTTP-тесты для `core_api.routers.courier`:
  - `GET /api/v1/courier/assignments/available` возвращает список AWAITING_COURIER (JOIN с `orders` для `address_snapshot`, `total`, `requested_time`).
  - `GET /api/v1/courier/assignments/mine` — только свои `COURIER_ASSIGNED` и `PICKED_UP`.
  - `POST /api/v1/courier/assignments/{id}/take` — вызывает `take_assignment`.
  - `POST /api/v1/courier/assignments/{id}/pickup` — вызывает `pickup_assignment` bridge.
  - `POST /api/v1/courier/assignments/{id}/deliver` — вызывает `deliver_assignment` bridge.
  - RBAC (INV-010): все пять маршрутов доступны ТОЛЬКО роли COURIER. Попытка из-под `customer_headers` / `barista_headers` / `admin_headers` → 403.
  - `AssignmentAlreadyTakenError` → 409; `AssignmentTransitionError(reason="not_owner")` → 403; `AssignmentTransitionError(reason="order_not_ready"|"forbidden_transition")` → 409; `assignment_not_found` → 404.
  - `main.py` регистрирует `courier_router` — тест инспектирует `app.router.routes`.
- Добавить `services/core-api/tests/test_delivery_assignment_optimistic_lock.py` — один тест на optimistic-lock семантику `take_assignment`:
  - Две независимые сессии на одну и ту же `assignment_id`. Первый вызов `take_assignment(aid, courier1, db1)` — успех. Второй вызов `take_assignment(aid, courier2, db2)` — поднимает `AssignmentAlreadyTakenError`. В базе остаётся `courier_id=courier1`, `status=COURIER_ASSIGNED`.
- Тесты MUST падать на текущем коде: нет ни enum `DeliveryAssignmentStatus`, ни модели `DeliveryAssignment`, ни миграции `0007`, ни сервиса `delivery_assignment`, ни роутера `courier`, ни функции `transition_order_bridge`. Ошибки будут ModuleNotFoundError / AttributeError / 404 RBAC / ImportError — все это валидные RED-состояния.

## Capabilities

### New Capabilities
- `delivery-assignment-tests`: RED-cycle pytest-сьют, фиксирующий Delivery Assignment state machine, bridge в Order Lifecycle (§6.1 переходы READY→IN_DELIVERY и IN_DELIVERY→COMPLETED), optimistic-lock при «take», и courier-роутер. Покрывает §6.3 целиком + INV-010 + INV-016 + INV-004 (атомарность bridge).

### Modified Capabilities
<!-- None — `order-lifecycle-tests` остаётся как есть; это новый параллельный автомат. -->

## Impact

- **Code**: 4 новых тестовых файла в `services/core-api/tests/`. Продакшен-код в этом цикле не меняется.
- **APIs**: HTTP-эндпоинты курьера (`GET /api/v1/courier/assignments/available`, `GET /api/v1/courier/assignments/mine`, `POST /api/v1/courier/assignments/{id}/take|pickup|deliver`) объявляются в тестах, но не реализованы — реализация в `delivery-assignment-green`.
- **Dependencies**: новых runtime-зависимостей нет. Тесты используют существующие pytest / SQLAlchemy / httpx / unittest.mock.
- **Database**: нет миграций. Тесты используют `migrated_db_session` (PostgreSQL) — миграция `0007_delivery_assignments.py` ожидается, поэтому часть тестов будет падать на этапе сбора моделей; для in-memory sqlite (`conftest.py` создаёт метаданные через `Base.metadata.create_all`) модели тоже ожидаются. Тесты ОК-ево падают, пока GREEN не положит модель и миграцию.
- **Mocks**: `transition_order_bridge` и `_accrue_loyalty` — патч-поинты внутри модулей; `send_order_notification` патчится как в `test_order_lifecycle`; celery-таски не вовлечены (у delivery-assignment нет refund-цепочки в этой фиче).

## Non-Goals

- Никакого продакшен-кода: ни модели `DeliveryAssignment`, ни миграции `0007`, ни сервиса, ни роутера, ни изменений в `rbac_matrix.py` и `main.py`. Всё это — `delivery-assignment-green`.
- Никаких изменений в `order_lifecycle.transition_order` / `order_cancel.cancel_order` — рефакторинг на `transition_order_bridge` и встраивание хука AWAITING_COURIER land-ятся в GREEN.
- Не реализуется расчёт маршрута / гео-координаты / ETA — это отдельная фича (yandex-maps-proxy).
- Не реализуется push-уведомление курьеру при появлении нового AWAITING_COURIER — это отдельная фича (delivery-courier-notifications).
- Не меняем Order Lifecycle state machine §6.1 — только навешиваем side-effect хук на `PAID→PREPARING` и поднимаем `order.status` через bridge-вариант в том же commit’е.
- Нет frontend-тестов: courier-панель UI — отдельная фича `feat/courier-panel-ui`.
- Нет тестов на аудит-лог / историю присвоений курьеров — вне scope §6.3.

## MVP Phase

Phase 4 — Delivery (PDD §7.1). Опирается на Phase 3 (§6.1 Order Lifecycle, §7.6 Cancellation Chain уже в main).
