## Why

Phase 6.1 (`READY → COMPLETED` auto-row, PDD §6.1) и §7.1 Phase 6 item 4 требуют
автозакрытия pickup-заказов по таймеру: после `auto_close_minutes` в READY
заказ должен автоматически переходить в `COMPLETED` с `auto_completed=true`,
`auto_completed_at` и триггером loyalty accrual — без SMS-уведомления.
Сегодня этой логики нет:

- `services/core-api/src/core_api/celery_app.py` используется только как
  клиент (`send_task`), beat-расписание отсутствует.
- Нет отдельного core-api worker'а и scheduler-контейнера в docker-compose.
- `order_lifecycle.transition_order` требует `actor_role`, разрешённого в
  `_ALLOWED_ROLES`, и безусловно шлёт SMS — нет способа вызвать переход от
  имени системы без нотификации.

Это **RED-фаза TDD-цикла**: вводит failing-тесты, фиксирующие контракт
сервисного слоя `pickup_autoclose`, Celery-таски `pickup.close_stale` и
beat-расписания. Реализация и docker-compose diff — в GREEN-цикле
`pickup-autoclose-green`.

## What Changes

- Новые failing-тесты (все падают по ImportError/AttributeError):
  - `test_pickup_autoclose_service.py` — юнит-тесты на
    `core_api.services.pickup_autoclose.close_stale_pickups`:
    - нет pickup/READY → 0, no-op;
    - pickup/READY с `updated_at < cutoff` → COMPLETED, `auto_completed=true`,
      `auto_completed_at` выставлен;
    - pickup/READY с `updated_at > cutoff` → не тронут;
    - DELIVERY/READY → не тронут (только pickup);
    - pickup/PREPARING → не тронут (только READY);
    - loyalty accrual создан (LoyaltyTransaction type=ACCRUAL) как
      side-effect;
    - SMS-уведомление НЕ отправлено (`send_order_notification` mock не
      вызван);
    - параметризация на `auto_close_minutes=120`: 119 мин → не закрыт,
      121 мин → закрыт.
  - `test_pickup_autoclose_task.py` — регистрация Celery-таски
    `pickup.close_stale` в `celery_app.tasks` + eager-вызов дергает сервис.
  - `test_celery_beat_schedule.py` — `celery_app.conf.beat_schedule` имеет
    ключ `close-stale-pickups-every-60s` со `schedule=60.0` и `task=
    pickup.close_stale`.
- Не трогаем production-код (сервис, таска, celery_app, docker-compose),
  чтобы тесты реально провалились.

## Capabilities

### New Capabilities
- `pickup-autoclose`: сервис `pickup_autoclose.close_stale_pickups`,
  Celery-таска `pickup.close_stale`, beat-расписание every 60s,
  scheduler + core-api-worker контейнеры. RED-цикл добавляет только
  требования и failing-тесты; реализация — в GREEN.

### Modified Capabilities
<!-- none in RED -->

## Impact

- Test-only diff:
  `services/core-api/tests/test_pickup_autoclose_service.py`,
  `test_pickup_autoclose_task.py`, `test_celery_beat_schedule.py`.
- Возможно: фабричный хелпер `make_pickup_ready_order(db, updated_at=...)` в
  `tests/_factories/orders.py` (не production-код).
- Non-Goals:
  - Реализация `services/pickup_autoclose.py` и `tasks/pickup_autoclose.py`
    — GREEN-цикл.
  - Изменение `celery_app.py` и docker-compose — GREEN.
  - SMS-уведомление о авто-закрытии — запрещено (§6.1 row, notifications
    column пуста).
  - Изменение частоты Beat (60s — фиксировано).
  - Регистрация таски в payment-worker/sms-worker (boundary violation).
  - Admin-UI авто-закрытия — отдельный тикет.
- MVP Phase: **6 (Admin Panel)**, item 4 (auto-close pickup).
- Inviolable Rules: INV-010 (role isolation — нужен actor='system'),
  INV-016 (only explicit transitions — READY→COMPLETED auto row).
- PDD refs: §6.1 (`READY → COMPLETED` auto row), §7.1 Phase 6 item 4.
