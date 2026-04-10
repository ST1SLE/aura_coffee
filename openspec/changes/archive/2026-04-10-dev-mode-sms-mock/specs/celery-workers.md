## celery-workers

### MODIFIED: SMS delivery with dev-mode bypass
- **Previously:** `send_sms()` always calls SMS.ru API; fails silently if API key is invalid
- **Now:** `send_sms()` checks `smsru_api_key` first; if empty, logs phone + message at WARNING level with "DEV" prefix and returns `True` without HTTP call
