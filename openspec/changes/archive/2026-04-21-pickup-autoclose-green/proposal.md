## Why

RED-цикл `pickup-autoclose-red` ввёл 15 failing-тестов, фиксирующих контракт
автозакрытия pickup-заказов (PDD §6.1 row "READY → COMPLETED — Автозакрытие
по таймеру", §7.1 Phase 6 item 4). Эта change — **GREEN-фаза TDD-цикла**:
реализует production-код, чтобы RED-тесты стали зелёными, и добавляет
runtime-инфраструктуру (Celery Beat + core-api-worker контейнеры).

Без этой change pickup-заказы остаются навечно в READY, если бариста забыл
нажать "Выдан" — а PDD §6.1 явно требует fallback-автозакрытия по
`shop_settings.auto_close_minutes` с триггером loyalty accrual и без SMS.

## What Changes

- **Сервис** `core_api.services.pickup_autoclose.close_stale_pickups(db, now)
  -> int`:
  - SELECT `orders` WHERE `type=pickup AND status=READY AND updated_at <
    now - auto_close_minutes`;
  - для каждого: transition → COMPLETED через `order_lifecycle`
    (reuse existing single-entry-point, INV-016), проставить
    `auto_completed=true`, `auto_completed_at=now`;
  - триггерит loyalty accrual (via existing `_accrue_loyalty`) и
    ПОДАВЛЯЕТ SMS-нотификацию.
- **Order lifecycle patch**: расширяем `_ALLOWED_ROLES[(READY, COMPLETED)]`
  ролью `"system"` и в `transition_order` при `actor_role == "system"`
  пропускаем `send_order_notification`. Остальные переходы роль `system`
  по-прежнему не допускает.
- **Celery task** `core_api.tasks.pickup_autoclose.close_stale_pickups_task`
  с именем `"pickup.close_stale"` — тонкая обёртка вокруг сервиса.
- **celery_app.py**: `include=["core_api.tasks.pickup_autoclose"]` +
  `beat_schedule["close-stale-pickups-every-60s"] = {task, schedule: 60.0}`.
- **docker-compose.yml**: два новых сервиса
  - `scheduler` — `celery -A core_api.celery_app beat --loglevel=info`;
  - `core-api-worker` — `celery -A core_api.celery_app worker
    --concurrency=2 --loglevel=info`.
  Оба используют образ `core-api` (тот же Dockerfile target `dev`).
- Все RED-тесты становятся green.

## Capabilities

### New Capabilities
<!-- Pickup-autoclose capability добавлена в RED; GREEN её реализует и
синхронизирует в main specs при archive. Нет новых capabilities в этой change. -->

### Modified Capabilities
- `pickup-autoclose`: GREEN реализует требования, которые RED зафиксировал
  как failing-тесты. Эта change — реализация контракта, не модификация.
  Выносим в sync-at-archive: спецификация `pickup-autoclose/spec.md` как
  ADDED (впервые появляется в main specs).

## Impact

- Production diff:
  - `services/core-api/src/core_api/services/pickup_autoclose.py` (new).
  - `services/core-api/src/core_api/tasks/__init__.py` (new, empty package).
  - `services/core-api/src/core_api/tasks/pickup_autoclose.py` (new).
  - `services/core-api/src/core_api/celery_app.py` (edit: include + beat).
  - `services/core-api/src/core_api/services/order_lifecycle.py` (edit:
    добавить `"system"` в allow-list READY→COMPLETED + suppress
    notification).
  - `docker-compose.yml` (2 new services).
- Tests: все из RED становятся green; возможно, pattern-match корректируем,
  но не содержание.
- Non-Goals:
  - Миграции — БД уже готова (0005 + 0008).
  - Admin-UI авто-закрытия — отдельный тикет, не в phase 6 order 4.
  - Prometheus-метрики/healthcheck на scheduler — отдельный тикет.
  - Cron в host-OS — запрещено (стандартизируем на Celery Beat).
  - SMS-уведомление о авто-закрытии — запрещено (§6.1 row).
  - Frequency override (env/admin panel) — 60s фиксировано.
- MVP Phase: **6 (Admin Panel)**, item 4 (auto-close pickup).
- Inviolable Rules: INV-010 (role isolation — `"system"` — служебная роль
  для scheduler, не пользователь), INV-016 (only explicit transitions —
  расширяем allow-list одним пунктом на уже-определённый переход).
- PDD refs: §6.1 row "READY → COMPLETED — Автозакрытие по таймеру",
  §7.1 Phase 6 item 4.
