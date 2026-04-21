## ADDED Requirements

<!-- GREEN-цикл реализует требования, зафиксированные как failing-тесты
в RED-цикле pickup-autoclose-red. При archive эта спека синхронизируется
в main specs (openspec/specs/pickup-autoclose/spec.md) — это первая
её публикация в main. -->

### Requirement: Service `close_stale_pickups` auto-closes stale pickup/READY orders

References: PDD §6.1 row "READY → COMPLETED — Автозакрытие по таймеру
(pickup)", §7.1 Phase 6 item 4, INV-003, INV-016.

The system SHALL expose
`core_api.services.pickup_autoclose.close_stale_pickups(db: Session, now:
datetime) -> int` that:

- reads `shop_settings.auto_close_minutes` (singleton row);
- selects `orders` rows WHERE `type = 'pickup'` AND `status = 'ready'`
  AND `updated_at < now - timedelta(minutes=auto_close_minutes)`;
- for each such row, transitions it to `COMPLETED` through
  `order_lifecycle` (reusing the single-entry-point state machine —
  INV-016), sets `auto_completed = true` and `auto_completed_at = now`,
  and triggers loyalty accrual (INV-003) as a side-effect of
  `order_lifecycle`;
- SHALL NOT send any SMS/in-app notification for auto-closures
  (§6.1 row — notifications column is empty);
- returns the number of closed orders.

#### Scenario: No pickup/READY orders — no-op
- **WHEN** `close_stale_pickups(db, now)` runs on a DB without any
  `(type=pickup, status=READY)` orders
- **THEN** the return value is `0` and no rows are modified

#### Scenario: Stale pickup/READY is closed
- **WHEN** a `(type=pickup, status=READY)` order has
  `updated_at = now - 61 minutes` and `auto_close_minutes = 60`
- **THEN** after `close_stale_pickups(db, now)` the order has
  `status = COMPLETED`, `auto_completed = true`,
  `auto_completed_at = now`, and the return value is `1`

#### Scenario: Fresh pickup/READY is skipped
- **WHEN** a `(type=pickup, status=READY)` order has
  `updated_at = now - 30 minutes` and `auto_close_minutes = 60`
- **THEN** the order is unchanged (`status = READY`,
  `auto_completed = false`) and the return value is `0`

#### Scenario: DELIVERY/READY is not touched
- **WHEN** a `(type=delivery, status=READY)` order is older than the
  cutoff
- **THEN** the order is unchanged (auto-close applies only to PICKUP)

#### Scenario: PICKUP/PREPARING is not touched
- **WHEN** a `(type=pickup, status=PREPARING)` order is older than the
  cutoff
- **THEN** the order is unchanged (auto-close applies only to READY)

#### Scenario: Loyalty accrual fires on auto-close
- **WHEN** a stale pickup/READY order with positive
  `total - delivery_fee` is auto-closed under `loyalty_percent = 10`
- **THEN** exactly one `LoyaltyTransaction` of type `ACCRUAL` is
  created with `amount = floor((total - delivery_fee) * 10 / 100)` and
  the corresponding `LoyaltyAccount.balance` increases by that amount

#### Scenario: No SMS/in-app notification is sent
- **WHEN** a stale pickup/READY order is auto-closed
- **THEN** `core_api.services.order_notifications.send_order_notification`
  is not invoked for that order

#### Scenario: Cutoff respects auto_close_minutes
- **WHEN** `auto_close_minutes = 120` and a pickup/READY order has
  `updated_at = now - 119 minutes`
- **THEN** the order is not auto-closed

- **WHEN** `auto_close_minutes = 120` and a pickup/READY order has
  `updated_at = now - 121 minutes`
- **THEN** the order is auto-closed

### Requirement: Order lifecycle admits `"system"` actor for READY → COMPLETED with suppressed notification

References: PDD §6.1, INV-010, INV-016.

`core_api.services.order_lifecycle` SHALL extend
`_ALLOWED_ROLES[(READY, COMPLETED)]` with `"system"` in addition to
`{"barista", "admin"}`. When `transition_order` (or
`transition_order_bridge`) is called with `actor_role == "system"`,
`send_order_notification` SHALL NOT be invoked. The `"system"` role
SHALL NOT be admitted for any other transition. Existing `"barista"`
and `"admin"` behaviour (including SMS notification) SHALL remain
unchanged.

#### Scenario: System actor closes a stale pickup without SMS
- **WHEN** `transition_order(order_id, COMPLETED, "system", db)` runs
  on a `(type=pickup, status=READY)` order
- **THEN** the transition succeeds, the order becomes `COMPLETED`,
  loyalty accrual fires, and `send_order_notification` is not called

#### Scenario: System actor is rejected for other transitions
- **WHEN** `transition_order(order_id, PREPARING, "system", db)` is
  attempted on a `(status=PAID)` order
- **THEN** `OrderTransitionError` is raised with `reason =
  "role_not_allowed"` and the order is unchanged

#### Scenario: Barista and admin behaviour unchanged
- **WHEN** `transition_order(order_id, COMPLETED, "barista", db)` runs
  on a `(type=pickup, status=READY)` order
- **THEN** the transition succeeds and `send_order_notification` IS
  invoked exactly once

### Requirement: Celery task `pickup.close_stale` wraps the service

References: PDD §7.1 Phase 6 item 4.

The system SHALL register a Celery task named `pickup.close_stale`
(module `core_api.tasks.pickup_autoclose`, loaded via `celery_app`'s
`include` list) that:

- opens a DB session via `SessionLocal()`;
- calls `close_stale_pickups(db, datetime.now(timezone.utc))`;
- returns the service's return value.

The task is a thin wrapper — business logic lives in the service to
keep Celery-independent tests possible.

#### Scenario: Task is registered under the expected name
- **WHEN** the core-api app boots and `celery_app` is imported
- **THEN** `"pickup.close_stale"` is present in `celery_app.tasks`

#### Scenario: Task invocation delegates to the service
- **WHEN** the task is applied in eager mode (`.apply()` /
  `.delay()` with `task_always_eager = True`)
- **THEN** `core_api.services.pickup_autoclose.close_stale_pickups` is
  called exactly once with a `Session` and a UTC-aware `datetime`

### Requirement: Celery Beat schedule fires `pickup.close_stale` every 60 seconds

References: PDD §6.1 row auto-close, §7.1 Phase 6 item 4.

The system SHALL declare a `beat_schedule` entry in
`core_api.celery_app.celery_app.conf` named
`close-stale-pickups-every-60s` with `task = "pickup.close_stale"` and
`schedule = 60.0` seconds. The frequency SHALL be hard-coded in code
(no runtime override) for scheduler determinism.

#### Scenario: Beat schedule key exists
- **WHEN** `celery_app.conf.beat_schedule` is read
- **THEN** it contains the key `"close-stale-pickups-every-60s"`

#### Scenario: Beat schedule entry points to the task with 60s interval
- **WHEN** that entry is read
- **THEN** `entry["task"] == "pickup.close_stale"` and
  `entry["schedule"] == 60.0`

### Requirement: docker-compose provides `scheduler` and `core-api-worker` services

References: PDD §7.1 Phase 6 item 4, AGENTS.md boundaries §Scope.

The top-level `docker-compose.yml` SHALL declare two services that
share the core-api Dockerfile (same `build.context`, same
`dockerfile: services/core-api/Dockerfile`, `target: dev`), mount the
same volumes as `core-api`, and read the same `env_file`:

- `scheduler`: `command = ["celery", "-A", "core_api.celery_app",
  "beat", "--loglevel=info"]`, `depends_on: [redis (healthy)]`.
- `core-api-worker`: `command = ["celery", "-A",
  "core_api.celery_app", "worker", "--loglevel=info",
  "--concurrency=2"]`, `depends_on: [redis (healthy), postgres
  (healthy), db-seed (completed_successfully)]`.

Beat and worker SHALL run in separate containers (Celery "-B" combined
mode is a production anti-pattern). Neither container SHALL register
this task inside payment-worker / sms-worker (boundary violation).

#### Scenario: scheduler service defined
- **WHEN** `docker compose config` is run on the repo root
- **THEN** the rendered config includes a service named `scheduler`
  with command starting with `celery -A core_api.celery_app beat`

#### Scenario: core-api-worker service defined
- **WHEN** `docker compose config` is run on the repo root
- **THEN** the rendered config includes a service named
  `core-api-worker` with command starting with
  `celery -A core_api.celery_app worker`
