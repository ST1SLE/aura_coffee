## Why

RED-цикл `delivery-assignment-red` уже зафиксировал 60 падающих тестов для Delivery Assignment Lifecycle (PDD §6.3, INV-010, INV-016, INV-004). Сейчас тесты падают с `ModuleNotFoundError` / `AttributeError`, потому что нет ни enum'а `DeliveryAssignmentStatus`, ни модели `DeliveryAssignment`, ни миграции, ни сервиса `delivery_assignment`, ни роутера `courier`, ни bridge-функции `transition_order_bridge`. GREEN-цикл доводит все 60 тестов до зелёного.

## What Changes

- Добавить `shared.enums.DeliveryAssignmentStatus` (AWAITING_COURIER, COURIER_ASSIGNED, PICKED_UP, DELIVERED, CANCELLED).
- Добавить модель `shared.models.delivery_assignment.DeliveryAssignment`: UUID pk, `order_id` FK→orders.id UNIQUE, `courier_id` FK→staff_accounts.id nullable, статус enum, временные метки (`assigned_at`, `picked_up_at`, `delivered_at`, `cancelled_at`, `created_at`, `updated_at`). Регистрация в `shared/models/__init__.py`.
- Добавить миграцию `database/alembic/versions/0007_delivery_assignments.py`: таблица + native enum `delivery_assignment_status` + UNIQUE на `order_id` + partial index `(status) WHERE status='awaiting_courier'`.
- Рефакторинг `core_api.services.order_lifecycle`: вынести `_apply_transition(order_id, new_status, actor_role, db) -> Order` (без commit, без notify), `transition_order` (с commit + notify) делегирует в `_apply_transition`, ДОБАВИТЬ публичную `transition_order_bridge(order_id, new_status, actor_role, db) -> Order` (без commit, без notify, для вызова изнутри delivery_assignment в той же txn). PAID→PREPARING для DELIVERY-заказа создаёт `DeliveryAssignment(AWAITING_COURIER)` хук'ом ВНУТРИ `_apply_transition` (а значит — для обоих оборачивающих функций).
- Добавить `core_api.services.delivery_assignment`:
  - `AssignmentTransitionError(Exception)` с полем `reason`.
  - `AssignmentAlreadyTakenError(AssignmentTransitionError)` (`reason="already_taken"`).
  - `take_assignment(aid, cid, db)` — optimistic lock через `UPDATE ... WHERE status=AWAITING_COURIER RETURNING ...`.
  - `pickup_assignment(aid, cid, db)` — проверяет `assignment.status=COURIER_ASSIGNED`, `courier_id==cid`, `order.status=READY`; вызывает `transition_order_bridge` (без commit), затем `db.commit()`.
  - `deliver_assignment(aid, cid, db)` — аналогично, с переходом order'а IN_DELIVERY→COMPLETED (внутри `_apply_transition` сработает `_accrue_loyalty`).
  - `cancel_assignment_for_order(order_id, db)` — для AWAITING/COURIER_ASSIGNED → CANCELLED; для PICKED_UP/DELIVERED — no-op (return None).
  - `list_available_for_courier(db)` — JOIN с orders, возвращает список view-объектов.
- Добавить `core_api.routers.courier`: `APIRouter(prefix="/api/v1/courier", tags=["courier"])` с 5 эндпоинтами; маппинг ошибок: `not_owner`→403, `forbidden_transition`/`order_not_ready`/`already_taken`→409, `assignment_not_found`→404. Регистрация в `core_api.main`.
- Добавить записи в `core_api.rbac_matrix.ROUTE_MATRIX` для всех 5 путей: `{COURIER}` (только курьер).
- В `order_cancel.cancel_order` добавить вызов `cancel_assignment_for_order` ДО `send_order_notification` (тест 2.8 — атомарность через текущий `db_session`).

## Capabilities

### New Capabilities
- `delivery-assignment`: production-код Delivery Assignment Lifecycle — модель, миграция, сервис, роутер, RBAC, bridge в Order Lifecycle. Реализует PDD §6.3 целиком + INV-004 + INV-010 + INV-016.

### Modified Capabilities
<!-- order-lifecycle / order-cancel рефакторятся, но ИХ требования не меняются — только внутренняя структура (extract `_apply_transition`, добавить `transition_order_bridge`, добавить `cancel_assignment_for_order` в цепочку отмены). Существующие тесты `test_order_lifecycle.py` / `test_order_cancel.py` остаются зелёными. -->

## Impact

- **Code**: 1 новый enum, 1 новая модель, 1 новая миграция, 1 новый сервис, 1 новый роутер, правки в `order_lifecycle`/`order_cancel`/`main`/`rbac_matrix`/`shared/models/__init__`. Никаких frontend-изменений (UI — отдельная фича `feat/courier-panel-ui`).
- **APIs**: 5 новых HTTP-эндпоинтов под `/api/v1/courier/...`, доступны только роли COURIER.
- **Database**: 1 новая таблица `delivery_assignments` + native enum `delivery_assignment_status` + UNIQUE/partial индексы. Миграция 0007.
- **Dependencies**: новых runtime-зависимостей нет.
- **Tests**: 60 RED-тестов из `delivery-assignment-red` становятся зелёными. Все существующие тесты (`test_order_lifecycle`, `test_order_cancel`, etc.) ОСТАЮТСЯ зелёными.

## Non-Goals

- Frontend-курьерская панель (UI — отдельная фича `feat/courier-panel-ui`).
- Гео-расчёт ETA / маршрута / автоназначение курьеров — отдельная фича `yandex-maps-proxy`.
- Push-уведомление курьеру при появлении нового AWAITING_COURIER — отдельная фича `delivery-courier-notifications`.
- История присвоений (audit trail) и метрики per-courier — вне scope §6.3.
- Изменения в Order Lifecycle state machine §6.1: только side-effect хук на PAID→PREPARING и bridge-вариант перехода — никакие новые переходы или роли не добавляются.

## MVP Phase

Phase 4 — Delivery (PDD §7.1).
