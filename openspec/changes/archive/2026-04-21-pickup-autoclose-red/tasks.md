## 1. Prereqs (no TDD)

- [x] 1.1 [core-api] PREREQ: Confirm `shared.models.order.Order` has
  `auto_completed: bool` and `auto_completed_at: datetime | None`
  (migration 0005). Report only — no code change.
- [x] 1.2 [core-api] PREREQ: Confirm
  `shared.models.shop_settings.ShopSettings` has `auto_close_minutes:
  int` with default 60 (migration 0008). Report only.
- [x] 1.3 [core-api] PREREQ: Grep existing usages of
  `celery_app.conf.beat_schedule` across `services/` and confirm no
  pre-existing entries — the RED test relies on absence of the key.

## 2. RED: service `close_stale_pickups` — shape & no-op

- [x] 2.1 [core-api] RED: Create
  `services/core-api/tests/test_pickup_autoclose_service.py` with
  `test_no_stale_orders_returns_zero` — seeds a ShopSettings row
  (`auto_close_minutes=60`) and zero orders, then calls
  `core_api.services.pickup_autoclose.close_stale_pickups(db, now)`.
  Asserts `return value == 0`. Must fail with `ImportError` (module
  does not exist yet).

## 3. RED: service — positive closure

- [x] 3.1 [core-api] RED: Add `test_stale_pickup_ready_is_completed`
  to `test_pickup_autoclose_service.py` — inserts pickup/READY order
  with `updated_at = now - 61 min` under `auto_close_minutes=60`,
  calls the service, then asserts `order.status == COMPLETED`,
  `order.auto_completed is True`, `order.auto_completed_at == now`,
  and return value `== 1`. Must fail (ImportError).

## 4. RED: service — negative filters

- [x] 4.1 [core-api] RED: Add `test_fresh_pickup_ready_is_skipped` —
  pickup/READY with `updated_at = now - 30 min`, `auto_close_minutes=
  60` → order unchanged, return `0`. Must fail.
- [x] 4.2 [core-api] RED: Add `test_delivery_ready_is_skipped` —
  `(type=DELIVERY, status=READY)` older than cutoff → unchanged,
  return `0`. Must fail.
- [x] 4.3 [core-api] RED: Add `test_pickup_preparing_is_skipped` —
  `(type=PICKUP, status=PREPARING)` older than cutoff → unchanged,
  return `0`. Must fail.

## 5. RED: service — loyalty accrual side-effect

- [x] 5.1 [core-api] RED: Add `test_auto_close_fires_loyalty_accrual`
  to `test_pickup_autoclose_service.py` — seeds shop_settings with
  `loyalty_percent=10`, pickup/READY order with `total=20000`,
  `delivery_fee=0`, user with LoyaltyAccount. After auto-close
  asserts exactly one `LoyaltyTransaction` of type `ACCRUAL` exists
  with `amount = 2000` and LoyaltyAccount.balance incremented by 2000.
  Must fail.

## 6. RED: service — SMS suppression

- [x] 6.1 [core-api] RED: Add `test_auto_close_does_not_send_sms` —
  monkeypatches
  `core_api.services.order_notifications.send_order_notification`
  (or `core_api.celery_app.celery_app.send_task`) to a Mock, runs
  auto-close on a stale pickup/READY order, asserts the mock was NOT
  called. Must fail (service module does not exist).

## 7. RED: service — cutoff parametrization

- [x] 7.1 [core-api] RED: Add `test_cutoff_respects_auto_close_minutes`
  parametrized over `(auto_close_minutes, age_minutes, expected_
  closed)`:
  `(60, 59, False)`, `(60, 61, True)`, `(120, 119, False)`,
  `(120, 121, True)`. Must fail.

## 8. RED: Celery task registration & dispatch

- [x] 8.1 [core-api] RED: Create
  `services/core-api/tests/test_pickup_autoclose_task.py` with
  `test_task_registered_under_expected_name` — asserts
  `"pickup.close_stale" in celery_app.tasks`. Must fail (task module
  not imported by celery_app).
- [x] 8.2 [core-api] RED: Add `test_task_invokes_service` —
  `monkeypatch.setattr` on
  `core_api.services.pickup_autoclose.close_stale_pickups` to a Mock,
  sets `celery_app.conf.task_always_eager = True`, imports the task
  via `from core_api.tasks.pickup_autoclose import
  close_stale_pickups_task`, calls `.apply().get()`. Asserts the mock
  service was called once with `(Session, datetime)` positional args.
  Must fail (task module missing).

## 9. RED: Celery Beat schedule

- [x] 9.1 [core-api] RED: Create
  `services/core-api/tests/test_celery_beat_schedule.py` with
  `test_beat_schedule_has_pickup_autoclose_entry` — asserts
  `"close-stale-pickups-every-60s" in celery_app.conf.beat_schedule`.
  Must fail (key absent).
- [x] 9.2 [core-api] RED: Add
  `test_beat_schedule_entry_points_to_task_with_60s_interval` —
  asserts
  `celery_app.conf.beat_schedule["close-stale-pickups-every-60s"]
  ["task"] == "pickup.close_stale"` and `["schedule"] == 60.0`.
  Must fail.

## 10. Verify RED state

- [x] 10.1 [core-api] VERIFY: Run
  `pytest services/core-api/tests/test_pickup_autoclose_service.py
  services/core-api/tests/test_pickup_autoclose_task.py
  services/core-api/tests/test_celery_beat_schedule.py` and confirm
  every new test fails (ImportError, AttributeError, AssertionError
  — all acceptable RED states). Capture the summary for the commit
  body.
