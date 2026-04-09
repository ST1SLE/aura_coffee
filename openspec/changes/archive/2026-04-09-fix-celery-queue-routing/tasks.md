## 1. Worker Queue Configuration

- [x] 1.1 [sms-worker] Configure dedicated `sms` queue in `services/sms-worker/src/sms_worker/main.py` — add `task_queues = [Queue("sms")]` and `task_default_queue = "sms"`
- [x] 1.2 [payment-worker] Configure dedicated `payments` queue in `services/payment-worker/src/payment_worker/main.py` — add `task_queues = [Queue("payments")]` and `task_default_queue = "payments"`

## 2. Task Routing from Core-API

- [x] 2.1 [core-api] Add `queue="sms"` to `send_task()` call in `services/core-api/src/core_api/routers/auth.py`

## 3. Verification

- [x] 3.1 [sms-worker] Verify sms-worker startup banner shows `sms` queue instead of `celery`
- [x] 3.2 [payment-worker] Verify payment-worker startup banner shows `payments` queue instead of `celery`
- [x] 3.3 [core-api] End-to-end test: `docker compose up` → send OTP → confirm sms-worker logs the code on first attempt
