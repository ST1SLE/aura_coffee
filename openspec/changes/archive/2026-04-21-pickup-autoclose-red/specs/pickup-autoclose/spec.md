## ADDED Requirements

### Requirement: Service `close_stale_pickups` auto-closes stale pickup/READY orders

References: PDD §6.1 row "READY → COMPLETED — Автозакрытие по таймеру
(pickup)", §7.1 Phase 6 item 4, INV-016.

The system SHALL expose
`core_api.services.pickup_autoclose.close_stale_pickups(db: Session, now:
datetime) -> int` that:

- reads `shop_settings.auto_close_minutes` (singleton row, default 60);
- selects `orders` rows WHERE `type = 'pickup'` AND `status = 'ready'`
  AND `updated_at < now - timedelta(minutes=auto_close_minutes)`;
- for each such row, transitions it to `COMPLETED`, sets
  `auto_completed = true` and `auto_completed_at = now`, and triggers the
  loyalty accrual side-effect (LoyaltyTransaction type=ACCRUAL) per
  `order_lifecycle`;
- SHALL NOT send any SMS/in-app notification for auto-closures
  (§6.1 row — notifications column is empty);
- returns the number of closed orders.

#### Scenario: No pickup/READY orders — no-op
- **WHEN** `close_stale_pickups(db, now)` runs on a DB without any
  `(type=pickup, status=READY)` orders
- **THEN** the return value is `0` and no rows are modified

#### Scenario: Stale pickup/READY is closed
- **WHEN** there is a `(type=pickup, status=READY)` order with
  `updated_at = now - 61 minutes` and `auto_close_minutes = 60`
- **THEN** after `close_stale_pickups(db, now)` the order has
  `status = COMPLETED`, `auto_completed = true`,
  `auto_completed_at = now`, and the return value is `1`

#### Scenario: Fresh pickup/READY is skipped
- **WHEN** there is a `(type=pickup, status=READY)` order with
  `updated_at = now - 30 minutes` and `auto_close_minutes = 60`
- **THEN** the order is unchanged (`status = READY`,
  `auto_completed = false`) and the return value is `0`

#### Scenario: DELIVERY/READY is not touched
- **WHEN** there is a `(type=delivery, status=READY)` order older than
  the cutoff
- **THEN** the order is unchanged (auto-close applies only to PICKUP)

#### Scenario: PICKUP/PREPARING is not touched
- **WHEN** there is a `(type=pickup, status=PREPARING)` order older than
  the cutoff
- **THEN** the order is unchanged (auto-close applies only to READY)

#### Scenario: Loyalty accrual fires on auto-close
- **WHEN** a stale pickup/READY order with a positive
  `total - delivery_fee` is auto-closed
- **THEN** exactly one `LoyaltyTransaction` of type `ACCRUAL` is created
  for that order and the corresponding `LoyaltyAccount.balance` increases
  by `floor((total - delivery_fee) * loyalty_percent / 100)`

#### Scenario: No SMS/in-app notification is sent
- **WHEN** a stale pickup/READY order is auto-closed
- **THEN** `core_api.services.order_notifications.send_order_notification`
  is not invoked for that order (no SMS task is enqueued)

#### Scenario: auto_close_minutes=120 cutoff at 119 minutes
- **WHEN** `auto_close_minutes = 120` and a pickup/READY order has
  `updated_at = now - 119 minutes`
- **THEN** the order is not auto-closed

#### Scenario: auto_close_minutes=120 cutoff at 121 minutes
- **WHEN** `auto_close_minutes = 120` and a pickup/READY order has
  `updated_at = now - 121 minutes`
- **THEN** the order is auto-closed

### Requirement: Celery task `pickup.close_stale` wraps the service

The system SHALL register a Celery task named `pickup.close_stale`
(module `core_api.tasks.pickup_autoclose`, imported via
`celery_app.include`) that:

- opens a DB session (`SessionLocal()` or equivalent);
- calls `close_stale_pickups(db, datetime.now(timezone.utc))`;
- returns the service's return value (number of closed orders).

The task is a thin wrapper — business logic lives in the service so
tests can exercise it without Celery.

#### Scenario: Task is registered under the expected name
- **WHEN** the core-api app boots and `celery_app` is imported
- **THEN** `"pickup.close_stale"` is present in `celery_app.tasks`

#### Scenario: Task invocation delegates to the service
- **WHEN** the task is applied in eager mode (`.apply()` or `.delay()`
  with `task_always_eager = True`)
- **THEN** `core_api.services.pickup_autoclose.close_stale_pickups` is
  called exactly once with a `Session` and a UTC-aware `datetime`

### Requirement: Celery Beat schedule fires `pickup.close_stale` every 60 seconds

The system SHALL declare a `beat_schedule` entry in
`core_api.celery_app.celery_app.conf` named
`close-stale-pickups-every-60s` with `task = "pickup.close_stale"` and
`schedule = 60.0` seconds. The frequency SHALL be hard-coded in code
(no runtime override) to keep the scheduler deterministic and
consistent with the worker stack.

#### Scenario: Beat schedule key exists
- **WHEN** `celery_app.conf.beat_schedule` is read
- **THEN** it contains the key `"close-stale-pickups-every-60s"`

#### Scenario: Beat schedule points at the task with 60s interval
- **WHEN** `celery_app.conf.beat_schedule["close-stale-pickups-every-
  60s"]` is read
- **THEN** its `"task"` value equals `"pickup.close_stale"` and its
  `"schedule"` value equals `60.0`
