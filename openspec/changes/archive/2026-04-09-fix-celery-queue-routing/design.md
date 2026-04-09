## Context

**Affected modules:** [core-api], [payment-worker], [sms-worker]

Both Celery workers consume from the default `celery` queue. When core-api publishes a task via `send_task()`, either worker can dequeue it. If the wrong worker grabs the message, it discards it as "unregistered task" — the message is permanently lost.

Current state:
- `sms-worker/main.py`: `Celery("sms_worker", broker=...)` — no queue config, defaults to `celery`
- `payment-worker/main.py`: `Celery("payment_worker", broker=...)` — no queue config, defaults to `celery`
- `core-api/routers/auth.py`: `celery_app.send_task(...)` — no `queue=` param, defaults to `celery`

## Goals / Non-Goals

**Goals:**
- Each worker SHALL consume exclusively from its own named queue
- Task publishers SHALL route messages to the correct queue
- No message loss due to wrong-worker consumption

**Non-Goals:**
- Changing broker transport (stays Redis)
- Adding task result backends or monitoring
- Refactoring core-api's ad-hoc Celery instantiation

## Decisions

### 1. Dedicated queues via `task_queues` + `task_default_queue`

Each worker configures its Celery app with:
```python
from kombu import Queue

celery_app.conf.task_queues = [Queue("sms")]
celery_app.conf.task_default_queue = "sms"
```

**Why `task_queues` over CLI `--queues` flag:** Keeps routing in code (versionable, reviewable) rather than in Dockerfile CMD args. Both approaches work; code-based is more explicit.

**Why not `task_routes`:** Routes are for mapping task names to queues on the publisher side. Here we need workers to listen on specific queues — `task_queues` is the correct mechanism.

### 2. Explicit `queue=` in `send_task()`

Core-api SHALL specify `queue="sms"` when publishing SMS tasks:
```python
celery_app.send_task("sms_worker.tasks.otp.send_otp_sms", args=[...], queue="sms")
```

This is simpler than configuring `task_routes` on the publisher, since core-api uses ad-hoc Celery instances.

### 3. Queue names: `sms` and `payments`

Short, lowercase, matching the service domain. No prefix needed — there are only two workers.

## Risks / Trade-offs

- **[Risk] Existing queued messages on upgrade** → Messages already in the `celery` queue will not be consumed by either worker after the change. Mitigation: drain or flush the default queue before deploying (`redis-cli DEL celery`). In dev, `docker compose down -v` handles this.
- **[Risk] Future workers forget to set a queue** → They'd default to `celery` and be isolated from existing workers. Acceptable — this is the safe default (no cross-contamination).
