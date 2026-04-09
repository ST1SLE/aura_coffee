## Why

Both Celery workers (sms-worker, payment-worker) consume from the same default `celery` queue. When core-api publishes an SMS task, either worker can grab it first. If payment-worker wins the race, it discards the message as "unregistered task" — the OTP SMS is silently lost. This is non-deterministic: restarts sometimes fix it by changing timing. This blocks MVP Phase 1 (Auth) reliability.

## What Changes

- Configure sms-worker to consume exclusively from a dedicated `sms` queue
- Configure payment-worker to consume exclusively from a dedicated `payments` queue
- Update core-api's `send_task()` calls to route tasks to the correct queue (`queue="sms"` for OTP tasks)

## Non-Goals

- Changing Celery broker from Redis to RabbitMQ or another transport
- Adding task result backends or monitoring (Flower, task events)
- Refactoring the ad-hoc `Celery(broker=...)` instantiation in core-api into a shared module

## Capabilities

### New Capabilities

_None_

### Modified Capabilities

- `celery-workers`: Workers SHALL consume from dedicated named queues instead of the default `celery` queue. Task routing from core-api SHALL specify the target queue explicitly.

## Impact

- **Backend**: `services/sms-worker/src/sms_worker/main.py`, `services/payment-worker/src/payment_worker/main.py`, `services/core-api/src/core_api/routers/auth.py`
- **Infrastructure**: No changes to docker-compose or Redis config required — Celery creates queues in Redis automatically
- **MVP Phase**: Phase 1 (Auth) — OTP delivery reliability

