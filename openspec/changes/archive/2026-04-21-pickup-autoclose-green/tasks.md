## 1. Prereqs (no TDD)

- [x] 1.1 [core-api] PREREQ: Grep `test_order_lifecycle.py` for
  `"system"` to confirm no existing test pins the role as rejected.
  If a test does — flag it and adjust accordingly (should be safe to
  skip adjustment if absent).

## 2. GREEN: order_lifecycle — allow `"system"` for READY→COMPLETED + suppress SMS

- [x] 2.1 [core-api] GREEN: Edit
  `services/core-api/src/core_api/services/order_lifecycle.py` —
  extend `_ALLOWED_ROLES[(OrderStatus.READY, OrderStatus.COMPLETED)]`
  from `frozenset({"barista", "admin"})` to
  `frozenset({"barista", "admin", "system"})`. Satisfies
  D2 / spec requirement "Order lifecycle admits system actor".
- [x] 2.2 [core-api] GREEN: In the same file, inside
  `transition_order`, skip `send_order_notification(order, new_status)`
  when `actor_role == "system"`. Commit behaviour unchanged.
  Satisfies D2.

## 3. GREEN: pickup_autoclose service

- [x] 3.1 [core-api] GREEN: Create
  `services/core-api/src/core_api/services/pickup_autoclose.py`
  with `close_stale_pickups(db: Session, now: datetime) -> int` —
  reads `ShopSettings.auto_close_minutes`, selects stale pickup/READY
  orders (dialect-conditional `FOR UPDATE SKIP LOCKED` under
  Postgres, plain select under SQLite), loops per-order inside
  `db.begin_nested()`, calls
  `transition_order_bridge(oid, OrderStatus.COMPLETED, "system", db)`,
  sets `auto_completed = True`, `auto_completed_at = now`, flushes.
  On per-order exception, rolls back the savepoint and continues.
  Commits once at the end. Returns count.
  Satisfies 3.1, 4.1, 4.2, 4.3, 5.1, 6.1, 7.1 RED tests
  (test_no_stale_orders_returns_zero,
  test_stale_pickup_ready_is_completed,
  test_fresh_pickup_ready_is_skipped,
  test_delivery_ready_is_skipped,
  test_pickup_preparing_is_skipped,
  test_auto_close_fires_loyalty_accrual,
  test_auto_close_does_not_send_sms,
  test_cutoff_respects_auto_close_minutes).

## 4. GREEN: tasks package + Celery task

- [x] 4.1 [core-api] GREEN: Create empty
  `services/core-api/src/core_api/tasks/__init__.py` (package marker).
- [x] 4.2 [core-api] GREEN: Create
  `services/core-api/src/core_api/tasks/pickup_autoclose.py` with
  `close_stale_pickups_task` decorated as
  `@celery_app.task(name="pickup.close_stale")` — opens
  `SessionLocal()`, calls
  `close_stale_pickups(db, datetime.now(timezone.utc))`, returns the
  count. Satisfies 8.1, 8.2 RED tests
  (test_task_registered_under_expected_name,
  test_task_invokes_service).

## 5. GREEN: celery_app include + beat_schedule

- [x] 5.1 [core-api] GREEN: Edit
  `services/core-api/src/core_api/celery_app.py` — construct `Celery`
  with `include=["core_api.tasks.pickup_autoclose"]` and
  `backend=settings.redis_url` (needed for eager-mode
  `AsyncResult.get()` in tests). Assign
  `celery_app.conf.beat_schedule = {
      "close-stale-pickups-every-60s": {
          "task": "pickup.close_stale",
          "schedule": 60.0,
      }
  }`. Satisfies 9.1, 9.2 RED tests
  (test_beat_schedule_has_pickup_autoclose_entry,
  test_beat_schedule_entry_points_to_task_with_60s_interval).

## 6. GREEN: docker-compose — scheduler + core-api-worker

- [x] 6.1 [core-api] GREEN: Edit `docker-compose.yml` — add
  `scheduler` service: same `build.context`, `dockerfile`,
  `target: dev`, `env_file`, `environment`, `volumes` as `core-api`;
  `command: ["celery", "-A", "core_api.celery_app", "beat",
  "--loglevel=info"]`; `depends_on: [redis (service_healthy)]`.
- [x] 6.2 [core-api] GREEN: In the same file, add `core-api-worker`
  service with identical build/env/volumes; `command: ["celery", "-A",
  "core_api.celery_app", "worker", "--loglevel=info",
  "--concurrency=2"]`; `depends_on: [redis (healthy), postgres
  (healthy), db-seed (completed_successfully)]`.

## 7. VERIFY

- [x] 7.1 [core-api] VERIFY: Run the three RED test files under
  Postgres (via `docker compose exec core-api pytest ...`) and
  confirm **all 15 tests pass**:
  `pytest services/core-api/tests/test_pickup_autoclose_service.py
  services/core-api/tests/test_pickup_autoclose_task.py
  services/core-api/tests/test_celery_beat_schedule.py -q`.
  Result: 15 passed.
- [x] 7.2 [core-api] VERIFY: Run the full
  `test_order_lifecycle.py` suite and confirm no regressions — the
  allow-list extension and `"system"`-based suppression must not break
  existing barista/admin happy paths or rejections.
  Result: 50 passed.
- [x] 7.3 [docker] VERIFY: Run `docker compose config --services` and
  confirm `scheduler` and `core-api-worker` appear in the output.
  Result: both present; containers running; end-to-end beat→worker
  fired `pickup.close_stale` successfully.
