## Why

Phase 3 (Order & Payment, PDD §7.1) ships with a `YukassaClient` hardcoded to call a real ЮKassa endpoint, and a `FastAPI` webhook app defined in `services/payment-worker/src/payment_worker/webhook.py` that `docker-compose.yml` never actually serves. The result: `docs/phase3_manual_test_scenarios.md` Block 4 cannot be executed without (a) real sandbox credentials, (b) an ngrok/cloudflared tunnel, and (c) manual clicking in the ЮKassa sandbox UI. This blocks reproducible local QA, blocks CI coverage of the payment lifecycle, and leaves a sharp edge where a misconfigured `.env` could point a live deployment at the sandbox — or, worse, leave `YUKASSA_BASE_URL` defaulted to production while secrets are empty.

SMS already solved this cleanly (`SMS_BACKEND=log`). Mirror that pattern for ЮKassa so developers and CI can exercise `create_payment → webhook → status=PAID → refund` end-to-end with zero external dependencies, while production continues to use the real client.

MVP phase: **Phase 3** (Order & Payment) — hardening the already-shipped capability.

## What Changes

- Add `YUKASSA_BACKEND` env var to `payment-worker` settings, `Literal["live", "fake"]`, default `"live"` in code. Dev `.env.example` ships with `fake`.
- Introduce `FakeYukassaClient` that returns a deterministic `payment_id` + in-cluster `confirmation_url`, and enqueues a Celery task (1s countdown) that POSTs a canonical `payment.succeeded` (or `refund.succeeded`) body to the local webhook endpoint. Fully self-driving — no human click, no tunnel.
- Centralise client construction behind a `get_yukassa_client()` factory inside `payment_worker.tasks`, so `create_payment` and `initiate_refund` pick up the backend toggle at call time.
- Deploy the existing webhook FastAPI app: add a `payment-webhook` service to `docker-compose.yml` running `uvicorn payment_worker.webhook:app --port 8241`. Expose 8241 on the host in `docker-compose.override.yml` for `curl`-based simulation (Block 4.3–4.8); keep it unexposed in base compose.
- Populate `.env.example` with the full `YUKASSA_*` block (backend, shop_id, secret_key, base_url, webhook_ips) using dev-safe defaults, and make `YUKASSA_WEBHOOK_IPS` honour `127.0.0.1` + in-cluster hostnames out of the box.
- Add a boot-time safety rail in `Settings`: refuse to start when `yukassa_backend == "live"` AND (`yukassa_shop_id` empty OR `yukassa_base_url` contains `test`/`sandbox`/`localhost`). Analogous to the existing `SMSRU_API_KEY` placeholder check (INV-015).
- Expose `yukassa_backend` in a lightweight `GET /health` on payment-webhook (and mirror into core-api health) so deploy smoke tests can assert `live` in production.

## Capabilities

### New Capabilities
- `payment-yukassa-backend`: Pluggable ЮKassa transport (live/fake) with a self-driving fake that emits canonical webhooks, a boot-time safety rail preventing live+misconfigured starts, and a served webhook endpoint wired into the dev stack.

### Modified Capabilities
(none — no existing spec under `openspec/specs/` owns payment-worker's ЮKassa transport contract; the prior RED/GREEN changes were archived without promoting specs)

## Impact

- **Code**: `services/payment-worker/src/payment_worker/{settings,tasks,yukassa_client}.py`; new `yukassa_fake.py`; new factory function; no changes to webhook handler logic.
- **Infra**: `docker-compose.yml` (new `payment-webhook` service), new `docker-compose.override.yml` for dev-only port exposure, `.env.example` additions.
- **Docs**: `docs/phase3_manual_test_scenarios.md` preamble updated — remove tunnel requirement, note that Block 4.2 now completes autonomously within ~2s.
- **CI**: unlocks running the Block 1–10 scenarios as a pytest job against the compose stack.
- **Prod safety**: Code default stays `live`; safety rail refuses ambiguous configs. No runtime cost when `backend=live` (fake module imported lazily inside the factory branch).
- **Out of scope**: changes to `YukassaClient` wire protocol, refund state-machine semantics, or any core-api / order-lifecycle behaviour — this is transport-layer only.

## Non-Goals

- Replacing the real `YukassaClient` or altering its HTTP contract with api.yookassa.ru.
- Supporting partial refunds, 3-D Secure challenges, or any ЮKassa feature not already in the live client.
- Record/replay against captured real ЮKassa traffic (the fake is hand-written, deterministic, and intentionally minimal).
- Gateway-abstraction for future non-ЮKassa providers — PDD §8.1 pins ЮKassa as the sole processor; revisit only if that changes.
- End-to-end browser automation of the checkout flow — this proposal makes the backend lifecycle testable; UI E2E is a separate concern.
