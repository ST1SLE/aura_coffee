## Why

The sms-worker Celery tasks are not discovered at runtime because `sms_worker/tasks.py` and `sms_worker/tasks/` coexist. Python's import system prioritizes the package (directory) over the module (file), so `import sms_worker.tasks` resolves to the empty `tasks/__init__.py`, shadowing `tasks.py` entirely. The `health_check` task is unreachable, and `autodiscover_tasks` cannot reliably find tasks in either location. This is a Phase 1 (Auth) blocker since OTP delivery depends on the sms-worker.

## What Changes

- Remove `sms_worker/tasks.py` — eliminate the namespace conflict
- Move the `health_check` task into the `tasks/` package (e.g., `tasks/__init__.py` or a dedicated module)
- Update `celery_app.autodiscover_tasks()` in `sms_worker/main.py` to correctly discover all task modules under `sms_worker.tasks`
- Verify existing `send_otp_sms` task in `tasks/otp.py` is discovered without changes

## Non-Goals

- Changing the SMS provider client (`clients/smsru.py`) or OTP logic — only fixing discovery
- Refactoring payment-worker task structure — it has no naming conflict
- Adding new Celery tasks or changing task signatures
- Modifying Docker/compose configuration — the worker start command is already correct

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `celery-workers`: The health_check task import path for sms-worker changes from `sms_worker.tasks.health_check` to `sms_worker.tasks.health.health_check` (or equivalent within the `tasks/` package). The requirement that each worker registers a health_check task remains, but the module location changes.

## Impact

- **Code**: `services/sms-worker/src/sms_worker/tasks.py` (removed), `tasks/__init__.py` or new module (health_check moved), `main.py` (autodiscover config)
- **Tests**: `test_otp_task.py` import paths may need updating if task module structure changes
- **Specs**: `celery-workers` spec scenario for sms-worker health_check import path
- **MVP Phase**: Phase 1 (Auth) — OTP delivery is gated on sms-worker functioning correctly
