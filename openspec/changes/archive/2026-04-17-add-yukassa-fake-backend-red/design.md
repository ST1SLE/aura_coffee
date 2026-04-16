## Context

Affected modules: **[payment-worker]**, **[infra]** (docker-compose, .env.example, nginx — nginx unchanged but noted), indirect impact on **[core-api]** health check only.

Phase 3 (Order & Payment, PDD §7.1, §8.1) shipped with:
- `services/payment-worker/src/payment_worker/yukassa_client.py` — single `httpx`-backed class hardcoded into `tasks.py:129-133, 185-189`.
- `services/payment-worker/src/payment_worker/webhook.py` — `FastAPI()` app defined but never served: the Dockerfile `CMD` is `celery … worker`, and `docker-compose.yml` exposes no port 8241.
- `settings.py` — `yukassa_base_url` defaults to `https://api.yookassa.ru/v3` (production); `yukassa_webhook_ips` parser only handles IPs/CIDRs, no wildcard.
- `.env.example` — zero `YUKASSA_*` entries, so a fresh clone boots with empty shop_id/secret.

SMS solved the equivalent problem at `services/sms-worker/src/sms_worker/settings.py:14` (`sms_backend: Literal["log","smsru"] = "log"`) and `tasks/{otp,notification}.py` via a module-level `_TRANSPORT` dispatch. We MUST replicate that pattern for ЮKassa.

Inviolable Rules in play: **INV-001** (prepay-only; the fake MUST still respect "no cash" semantics — a fake "success" is a modeled payment, not a skipped payment), **INV-004** (atomicity of points+promo+payment compensation — unchanged by this work), **INV-015** (secrets in env vars; safety rail refuses live-mode with empty secrets), **INV-016** (payment state machine — the fake MUST emit the same event shapes the live webhook handler already consumes).

## Goals / Non-Goals

**Goals:**
- Developers and CI SHALL exercise `CREATED → PAID → PREPARING → … → COMPLETED` and `PAID → CANCELLED → REFUNDED` end-to-end with no ЮKassa account, no tunnel, no manual clicks.
- Production SHALL default to the live client; misconfiguration SHALL fail fast at boot, not silently at first charge.
- `YukassaClient` wire protocol (the real HTTP client) SHALL NOT change — this is transport selection, not transport redesign.
- The webhook endpoint SHALL be served in the dev stack so manual simulation (`curl`) in Block 4.3–4.8 works identically to the fake's auto-driven path.

**Non-Goals:**
- Partial refunds, 3-D Secure, saved cards, recurring payments — not in `YukassaClient` today, not added here.
- Recording/replaying real ЮKassa fixtures — the fake is hand-written and minimal.
- A generic payment-gateway abstraction — PDD §8.1 pins ЮKassa; we wrap one provider only.
- UI-level E2E — this proposal unblocks backend lifecycle testing; browser automation is a separate change.

## Decisions

### D1: Factory function, not DI container

`payment_worker.tasks` SHALL gain a module-level `get_yukassa_client() -> YukassaClientProtocol` that branches on `settings.yukassa_backend`. `create_payment` and `initiate_refund` SHALL call the factory at task-execution time (not import time), so env changes between worker restarts take effect cleanly and pytest's `monkeypatch` on settings works without reloading modules.

**Alternatives considered:** (a) subclass `YukassaClient` with a `FakeYukassaClient(YukassaClient)` that overrides HTTP methods — rejected, couples fake to `httpx` machinery it doesn't use; (b) a full DI container (e.g. `dependency-injector`) — rejected, unnecessary weight for one swap point.

### D2: Fake self-drives webhooks via Celery

`FakeYukassaClient.create_payment()` SHALL return immediately with a deterministic `payment_id = f"fake_{uuid4().hex}"` and a `confirmation_url = f"http://localhost:${NGINX_PORT}/dev/yukassa-sandbox/{payment_id}"`, then call `yukassa_fake_callback.apply_async((payment_id, "payment.succeeded"), countdown=1)`. The Celery task MUST construct the canonical ЮKassa webhook body and `httpx.post` it to `http://payment-webhook:8241/webhooks/yukassa` (in-cluster DNS).

**Why in-band rather than synchronous:** goes through the exact same code path the real provider would — IP whitelist, event-id idempotency, DB transaction, cart cleanup. Anything the fake exercises, production exercises too. A synchronous call would bypass whitelist/idempotency and give false confidence.

**Alternatives considered:** (a) fake mutates the DB directly — rejected, skips `webhook.py` entirely, leaves that code path untested; (b) fake returns a URL to a dev-only core-api route with "Pay"/"Fail" buttons as the *only* path — rejected for automation, but retained as an *additional* affordance (see D5).

### D3: Failure modes are deterministic and env-driven

`FakeYukassaClient` SHALL honour a `YUKASSA_FAKE_OUTCOME` env var: `success` (default), `canceled`, `http_error`. `canceled` schedules `payment.canceled` instead of `payment.succeeded`. `http_error` raises `httpx.RequestError` synchronously from `create_payment`, exercising the existing `autoretry_for=(httpx.RequestError,)` branch and the `_fail_payment_and_cancel_order` compensation path (INV-004). This is the only way Block 4.7 ("payment failure retry + cancel") becomes reproducible without credential tampering.

### D4: Webhook runs as its own compose service

Add a `payment-webhook` service to `docker-compose.yml` with the same image as `payment-worker` but `command: ["uvicorn", "payment_worker.webhook:app", "--host", "0.0.0.0", "--port", "8241"]`. Depends on postgres + redis (same as `payment-worker`). Does NOT map port to host in base compose. A new `docker-compose.override.yml` (auto-loaded) maps `"8241:8241"` for dev so Block 4.3–4.8 `curl` commands work.

**Why a separate service vs. running uvicorn + celery in one container:** one-process-per-container keeps Dockerfile CMD unchanged for the celery worker, keeps logs separable, and matches how core-api already runs. The operational cost is one more entry in `docker compose ps`.

### D5: Confirmation URL resolves to a tiny dev-only page

The fake's `confirmation_url` SHALL point to `http://localhost:${NGINX_PORT}/dev/yukassa-sandbox/<payment_id>` — a static HTML page served by nginx (or a core-api route behind `settings.environment == "dev"`) with three buttons: "Auto-succeed in 1s (default)", "Simulate cancel", "Simulate HTTP error on next retry". Default behaviour is auto-succeed, so scripts don't need to open the URL. This covers manual-QA cases where the tester wants to pause the flow without editing env vars. **Implementation SHOULD start with the Celery-countdown path (D2) and add the HTML page in a follow-up task** — it is a convenience, not a blocker.

### D6: Safety rail in `Settings.model_validator`

```
if yukassa_backend == "live":
    if not yukassa_shop_id or not yukassa_secret_key:
        raise ValueError("…INV-015: live mode requires non-empty credentials")
    low = yukassa_base_url.lower()
    if any(m in low for m in ("test", "sandbox", "localhost", "127.0.0.1")):
        raise ValueError("…live mode with non-production base_url refused")
```

The process SHALL fail to start. No soft-warning. Analogous to `sms-worker/src/sms_worker/settings.py:17-24`.

### D7: `.env.example` defaults

```
YUKASSA_BACKEND=fake
YUKASSA_SHOP_ID=dev-shop
YUKASSA_SECRET_KEY=dev-secret
YUKASSA_BASE_URL=https://api.yookassa.ru/v3
YUKASSA_WEBHOOK_IPS=127.0.0.1,payment-worker,payment-webhook
YUKASSA_FAKE_OUTCOME=success
```

Plus expand `_is_whitelisted` to resolve hostnames (via `socket.gethostbyname`, cached once at process start) so `payment-worker`/`payment-webhook` entries work inside the compose network. Wildcard `*` is NOT supported — explicit is better than silently permissive, and the dev default already covers the in-cluster case.

### D8: Health check exposes backend

`GET /health` on payment-webhook (new) and on core-api (extend existing) SHALL return `{"yukassa_backend": "live"|"fake", ...}`. Deploy smoke tests SHALL assert `"live"` in prod. This is the belt-and-suspenders for the safety rail: even if boot somehow succeeded in a misconfigured state, the health endpoint exposes the truth.

## Atomicity Analysis (INV-004)

The fake is a drop-in for `YukassaClient.create_payment()` / `create_refund()`. Both are called *outside* DB transactions in `tasks.py:137-149, 190-201`. Atomicity of the compensation flow (`_fail_payment_and_cancel_order`) is therefore unchanged — the fake raising `httpx.RequestError` triggers the exact same retry+compensate path as a real ЮKassa outage. Success path: the fake-emitted webhook is processed by `webhook.py:_handle_payment_succeeded`, which already wraps Payment/Order/Loyalty/Notification updates in a single `session_scope` (one commit). No new atomicity boundaries are introduced.

## State Machine Impact (INV-016)

No transitions added or removed. The fake emits the existing `payment.succeeded` / `payment.canceled` / `refund.succeeded` events, consumed by the existing `dispatch_event` dispatcher. Payment status transitions (`PENDING → AWAITING_CONFIRMATION → SUCCEEDED`) and order status transitions (`CREATED → PAID`, `CREATED → CANCELLED`) are driven by the same code as production.

## Risks / Trade-offs

- **[Risk]** Fake and live diverge over time as the real ЮKassa API evolves → **Mitigation:** the fake is tiny (≤100 LOC) and only exercises three events — easy to audit quarterly against ЮKassa release notes. Dev's `YUKASSA_FAKE_OUTCOME` knob also keeps it honest about error paths.
- **[Risk]** Someone ships `YUKASSA_BACKEND=fake` to prod → **Mitigation:** two independent gates — (1) code default is `live`, (2) health endpoint exposes backend for deploy smoke test. Add a CI check that refuses `YUKASSA_BACKEND=fake` in any file under `deploy/prod/` (follow-up).
- **[Risk]** The 1s Celery countdown could race a fast test that polls `status=PAID` immediately → **Mitigation:** tests SHOULD poll with backoff up to ~5s; manual scenarios already specify "within ~5s". Alternative of `countdown=0` rejected because it loses the "asynchronous webhook" semantic the real system has.
- **[Trade-off]** Adding a new compose service (`payment-webhook`) increases local resource use slightly → acceptable; it's one uvicorn worker, <50MB RAM.
- **[Trade-off]** Hostname resolution in `_is_whitelisted` requires `socket` at import or request time → we cache at process start; if compose DNS changes (rare), the webhook restarts with the worker.

## Migration Plan

Forward-only; no schema changes, no data migration. Rollout:

1. Merge with code default `YUKASSA_BACKEND=live`. Existing prod `.env` files (which omit the var) continue to behave identically.
2. Update `.env.example` → `YUKASSA_BACKEND=fake`. Dev copies pick this up on next `cp .env.example .env`.
3. Deploy to staging with `live` + real sandbox creds; verify end-to-end still works.
4. Deploy to prod with `live` + real prod creds + real IP whitelist. Smoke test asserts `GET /health` → `yukassa_backend=live`.
5. **Rollback:** revert the commit. No state to unwind. Clients in-flight at rollback time: any `AWAITING_CONFIRMATION` Payment rows with `yukassa_payment_id` starting `fake_` in a prod DB would be unrecoverable — prevented by the D6 safety rail + D7 example-only fake defaults.

## Open Questions

- Does the dev-only HTML sandbox page (D5) belong on nginx or core-api? Leaning nginx (static, no auth coupling). Defer until after D2 lands.
- Should `YUKASSA_FAKE_OUTCOME` be per-call (header or request param) instead of process-wide env? Would make parallel test scenarios easier but adds API surface. Start with env var; promote if pytest workflows demand it.
