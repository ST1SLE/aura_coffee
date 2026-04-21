## Context

Affected modules: **[core-api]**, **[database]** (read-only — `orders`,
`shop_settings`, `loyalty_*`), **[redis]** (Celery broker).

Current state:
- `services/core-api/src/core_api/celery_app.py` объявляет только
  `Celery("core_api", broker=settings.redis_url)` — без `include`, без
  `beat_schedule`. Используется как клиент (`send_task`).
- `services/core-api/src/core_api/services/order_lifecycle.py` —
  `transition_order(order_id, new_status, actor_role, db)` жёстко
  валидирует `actor_role ∈ _ALLOWED_ROLES[(from, to)]` и безусловно вызывает
  `send_order_notification(order, new_status)`. Для READY→COMPLETED
  allow-list = `{barista, admin}` — `system` отсутствует. Side-effect
  `_accrue_loyalty` срабатывает на любом переходе в COMPLETED.
- Order-модель уже несёт `auto_completed`, `auto_completed_at` (миграция
  0005). ShopSettings уже имеет `auto_close_minutes` с дефолтом 60
  (миграция 0008).
- docker-compose.yml не содержит ни `scheduler` (beat), ни
  `core-api-worker`. Только payment-worker и sms-worker.

Эта change — **RED-фаза TDD**: вводит failing-тесты, фиксирующие контракт
будущего сервиса `pickup_autoclose`, Celery-таски и beat-расписания. GREEN-
цикл реализует код.

## Goals / Non-Goals

**Goals:**
- Зафиксировать контракт `services/pickup_autoclose.close_stale_pickups(db,
  now) -> int`: фильтр (type=pickup, status=READY, `updated_at < now -
  auto_close_minutes`), mutation (status=COMPLETED, `auto_completed=true`,
  `auto_completed_at=now`), side-effect (loyalty accrual) и отсутствие SMS.
- Зафиксировать контракт Celery-таски `pickup.close_stale` (регистрация,
  eager-вызов дергает сервис).
- Зафиксировать контракт beat-расписания (ключ `close-stale-pickups-every-
  60s`, `schedule=60.0`, `task="pickup.close_stale"`).
- Зафиксировать, что `auto_close_minutes=120` влияет на cutoff (119 мин
  не закрыт, 121 мин закрыт).

**Non-Goals:**
- Реализация сервиса, таски, изменений в celery_app.py — GREEN-цикл.
- docker-compose scheduler/core-api-worker сервисы — GREEN.
- Admin-UI для `auto_close_minutes` — уже сделан в shop-settings-admin-api.
- SMS/in-app нотификация авто-закрытия — запрещена (§6.1 row).
- Изменение частоты Beat — фиксировано 60s.
- Любые изменения payment-worker / sms-worker.

## Decisions

### D1: RED-only diff — только тесты, никакого production-кода

**Decision:** RED-цикл SHALL добавить только новые тестовые файлы
(`tests/test_pickup_autoclose_service.py`, `test_pickup_autoclose_task.py`,
`test_celery_beat_schedule.py`) плюс, при необходимости, фабричные хелперы
в `tests/_factories/`. Production-код (`services/pickup_autoclose.py`,
`tasks/`, `celery_app.py`) — не трогаем.

**Rationale:** цель RED — красный pytest-ран, который в GREEN станет
зелёным. Если писать skeleton производства до тестов — теряется сигнал
"тест ловит регрессию".

**Alternative rejected:** писать skeleton-реализацию + тесты одновременно.
Отклонено по тем же причинам, что и предыдущие RED-циклы (см.
`shop-settings-admin-api-red` D1, `admin-users-api-red`).

### D2: Failing по ImportError — импорт несуществующих модулей

**Decision:** тесты SHALL импортировать `core_api.services.pickup_autoclose`
и `core_api.tasks.pickup_autoclose`, которых ещё нет. ImportError —
приемлемый failure mode для RED.

**Rationale:** консистентно с RED-циклами phase 5/6 (order-history,
shop-settings, admin-users). GREEN добавляет модули и тесты зеленеют.

### D3: Контракт сервиса — чистая функция `close_stale_pickups(db, now) -> int`

**Decision:** сервис SHALL принимать явный `db: Session` и явный `now:
datetime` (UTC-aware), возвращая количество закрытых заказов. Тесты
подаут monotonic `now` через параметр, не через `datetime.now()` mock.

**Rationale:** testability. Taska — тонкая обёртка, подставляющая
`SessionLocal()` и `datetime.now(timezone.utc)`.

**Alternative rejected:** сервис читает `now` из freezegun / мок на
`datetime.now`. Отклонено — параметр `now` проще и не требует magic.

### D4: Подавление SMS через `actor='system'` (или `suppress_notifications=True`)

**Decision:** GREEN-реализация сервиса SHALL пройти переход через
`order_lifecycle.transition_order` с `actor_role='system'` (или добавить
флаг `suppress_notifications`). Текущий `_ALLOWED_ROLES[(READY, COMPLETED)]
= {barista, admin}` — нужно расширить до `{barista, admin, system}`, а
`system` SHALL подавлять `send_order_notification`.

В RED тесте этот контракт фиксируется так: `send_order_notification`
(или `celery_app.send_task`) мокается и проверяется `not_called()` после
`close_stale_pickups`.

**Rationale:** PDD §6.1 row "Автозакрытие по таймеру (pickup)" явно
указывает, что notifications column пуста — SMS запрещён.

**Alternative rejected:** прямая мутация `order.status = COMPLETED` в
сервисе, минуя order_lifecycle. Отклонено — ломает single-entry-point для
переходов (INV-016), теряет loyalty accrual side-effect.

### D5: Фабричный хелпер для pickup/READY с контролируемым `updated_at`

**Decision:** тесты SHALL либо добавить helper в
`tests/_factories/orders.py`, либо inline создавать Order с явным
`updated_at`. В RED — предпочтительно inline, чтобы помещение факт-
знания о колонках оставалось рядом с assert'ами.

**Rationale:** `updated_at` автоматически обновляется сервером при UPDATE.
Чтобы подделать старый `updated_at`, нужно либо вставить напрямую с
явным значением, либо после insert сделать `UPDATE orders SET
updated_at=... WHERE id=...` в обход ORM. Оба подхода валидны;
фабрика может предоставить хелпер позже.

### D6: Celery eager-mode для тестов таски

**Decision:** `test_pickup_autoclose_task.py` SHALL использовать
`celery_app.conf.task_always_eager = True` (на время теста, через
fixture/monkeypatch) и проверять, что `.apply()` или `.delay()` вызывает
сервис. Сервис мокается (`patch("core_api.services.pickup_autoclose.
close_stale_pickups")`).

**Rationale:** изолируем таску от сервиса — тест таски проверяет только
диспатч, не бизнес-логику (она под отдельным тестом).

### D7: Фильтр FOR UPDATE SKIP LOCKED — не тестируем в RED на SQLite

**Decision:** RED-тесты SHALL запускаться под in-memory SQLite (как все
текущие unit-тесты). SKIP LOCKED — Postgres-only, в SQLite no-op. Тест
SKIP LOCKED (если понадобится) SHALL быть помечен
`@pytest.mark.skipif(TEST_DATABASE_URL is sqlite)` и отложен на GREEN.

**Rationale:** RED-цикл фокусируется на бизнес-логике; concurrency-
инварианты — часть GREEN при необходимости.

## Risks / Trade-offs

- **[Risk]** `ImportError` от теста может блокировать даже collection-фазу
  pytest. → **Mitigation:** `pytest.importorskip`? Нет — мы ХОТИМ падение
  на collection, это и есть RED. Остальные тесты изолированы, не
  импортируют новый модуль.
- **[Risk]** Текущий `_ALLOWED_ROLES` не содержит `system` — если в RED
  тест дергает order_lifecycle напрямую, упадёт на `role_not_allowed`, а
  не на `ImportError`. → **Mitigation:** тест сервиса НЕ дергает
  order_lifecycle напрямую — дергает `close_stale_pickups`, которого
  ещё нет. ImportError приходит первым.
- **[Risk]** Тест beat_schedule: `celery_app.conf.beat_schedule` уже
  сейчас возвращает пустой dict (не AttributeError). → **Mitigation:**
  assert проверяет наличие ключа `close-stale-pickups-every-60s`; в RED
  ключа нет → KeyError → failing.
- **[Risk]** `send_order_notification` — модульная функция, mock на
  `celery_app.send_task` может не перехватить, если GREEN реализует
  suppress через early-return. → **Mitigation:** тест мокает
  `core_api.services.order_notifications.send_order_notification`
  (верхнеуровневая функция) и проверяет `not_called()`.

## Migration Plan

Миграций в RED нет — БД уже содержит `auto_completed`,
`auto_completed_at`, `auto_close_minutes` (0005 + 0008). GREEN-цикл не
добавляет новых миграций.

Forward-only. Rollback — удаление новых тестовых файлов (тесты не
вливались в production поведение).

## 152-FZ Compliance

Не применимо — сервис работает с `orders` и `shop_settings`, PII (user
profile) не касается. INV-013 не затрагивается.

## Open Questions

- Нужно ли в RED фиксировать конкретный механизм подавления SMS
  (`actor='system'` vs `suppress_notifications=True`)? → **Resolved:**
  RED-тест фиксирует только ИНВАРИАНТ (`send_order_notification`
  не вызван). Конкретный механизм выбирается в GREEN design — D4 выше
  говорит о предпочтении `actor='system'`.
- Добавить ли RED-тест на `FOR UPDATE SKIP LOCKED` под Postgres? →
  **Resolved:** отложено на GREEN (D7). В RED фокус на бизнес-логике
  сервиса.
