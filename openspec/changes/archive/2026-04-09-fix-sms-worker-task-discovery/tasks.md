## 1. Remove namespace conflict

- [x] 1.1 [sms-worker] Delete `services/sms-worker/src/sms_worker/tasks.py`

## 2. Move health_check task into package

- [x] 2.1 [sms-worker] Add `health_check` task to `services/sms-worker/src/sms_worker/tasks/__init__.py` (import `celery_app` from `sms_worker.main`, define `health_check` task returning `"ok"`)

## 3. Fix autodiscover configuration

- [x] 3.1 [sms-worker] Update `services/sms-worker/src/sms_worker/main.py`: change `autodiscover_tasks(["sms_worker", "sms_worker.tasks"])` to `autodiscover_tasks(["sms_worker.tasks"])`

## 4. Verify tests pass

- [x] 4.1 [sms-worker] Run existing tests (`pytest services/sms-worker/`) and confirm `send_otp_sms` and `health_check` are both discoverable
