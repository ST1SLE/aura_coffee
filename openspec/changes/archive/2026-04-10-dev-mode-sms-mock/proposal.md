## Why

The auth flow is untestable in local Docker Compose because `sms-worker` calls the real SMS.ru API which fails without a valid API key. The OTP status stays `"created"` instead of transitioning to `"sent"`, causing `verify-code` to return 409. This blocks all Phase 1 (Auth) manual testing.

## What Changes

- **[sms-worker]** When `smsru_api_key` is empty, `send_sms()` skips the HTTP call, logs the phone number and message to stdout, and returns `True`. This lets the OTP status transition to `"sent"` so `verify-code` works.

## Non-Goals

- No new environment variables or feature flags — empty API key is the signal
- No changes to core-api OTP logic, Celery task structure, or frontend code
- No mock/test infrastructure (pytest fixtures, test doubles) — this is runtime dev-mode behavior

## MVP Phase

Phase 1 (Auth) — unblocks local testing of the entire OTP verification flow.

## Capabilities

### New Capabilities
<!-- None — this modifies existing SMS delivery behavior -->

### Modified Capabilities
- `celery-workers`: SMS worker's `send_sms` function gains dev-mode bypass when API key is empty

## Impact

- **Code:** `services/sms-worker/src/sms_worker/clients/smsru.py` (single file)
- **Secrets:** No new secrets. Relies on existing `SMSRU_API_KEY` being empty in dev (INV-015)
- **Risk:** Minimal — only affects behavior when API key is explicitly absent
