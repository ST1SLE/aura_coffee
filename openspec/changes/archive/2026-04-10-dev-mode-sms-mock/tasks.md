## Tasks

### 1. Dev-mode SMS bypass

- [x] 1.1 [sms-worker] `services/sms-worker/src/sms_worker/clients/smsru.py` — add early return in `send_sms()`: if `settings.smsru_api_key` is falsy, log phone and message at WARNING level with "DEV" prefix, return `True`
