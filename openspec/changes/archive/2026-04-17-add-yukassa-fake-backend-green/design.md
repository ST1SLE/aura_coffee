## Context

Affected modules: **[payment-worker]** (implementation), **[core-api]** (health endpoint extension only), **[infra]** (docker-compose + .env.example). The technical background, decisions D1–D8, atomicity analysis, state-machine impact, risks, and migration plan are specified in the sibling RED change's `design.md` (`openspec/changes/add-yukassa-fake-backend-red/design.md`). This document captures the incremental implementation choices that are GREEN-specific.

## Goals / Non-Goals

**Goals:**
- Make every RED test in `add-yukassa-fake-backend-red` pass with minimal code.
- Ship a working dev stack where `./scripts/up.sh` → place order → `status=PAID` within ~2s, no external config.

**Non-Goals:**
- Re-deriving design rationale — see RED design.md.
- Refactoring unrelated code paths in payment-worker.

## Decisions

### D1: Minimal fake surface

`FakeYukassaClient` SHALL expose only the three methods `YukassaClient` exposes today (`create_payment`, `get_payment`, `create_refund`), with matching return shapes. No shared base class — structural typing via duck-typed call sites is sufficient; a `YukassaClientProtocol` in `yukassa_client.py` MAY be added if mypy complains.

### D2: Callback Celery task lives in `yukassa_fake.py`

The callback task SHALL be named `yukassa_fake_callback` (autodiscovered by the existing `celery_app.autodiscover_tasks(["payment_worker"])`). It SHALL use `httpx.Client` (sync) to POST the canonical webhook body to `http://payment-webhook:8241/webhooks/yukassa`. Timeout 5s. On any HTTP error it SHALL log and return; no retry — the test surface doesn't need it and retries would mask bugs.

### D3: Hostname resolution cached at process start

`_is_whitelisted` SHALL expand `yukassa_webhook_ips` entries once, at first call, by attempting `socket.gethostbyname(entry)` for any entry that is neither an IP nor a CIDR. Results cached in a module-level dict keyed by entry string. Resolution failures: entry silently dropped (log at DEBUG). This keeps the happy path allocation-free after warmup.

### D4: Health endpoints

- `payment-webhook` gets a new `@app.get("/health")` returning `{"status":"ok","yukassa_backend": settings.yukassa_backend}` — no DB round-trip, no Redis call.
- `core-api` existing `/health` SHALL be extended to include `yukassa_backend` by reading the same env var (`YUKASSA_BACKEND`) directly — core-api has no `payment_worker.settings` dependency and we don't introduce one; it's a single `os.getenv("YUKASSA_BACKEND", "live")` read.

### D5: docker-compose shape

New service `payment-webhook` copies `payment-worker`'s image (`target: dev`), mounts the same volumes, uses the same `env_file`, overrides only `command` and container name. `docker-compose.override.yml` (new file, auto-loaded by compose) maps `"8241:8241"`. Base `docker-compose.yml` does NOT map the port — prod uses a separate compose file (future) that likewise omits the mapping.

### D6: `.env.example` values

```
YUKASSA_BACKEND=fake
YUKASSA_SHOP_ID=dev-shop
YUKASSA_SECRET_KEY=dev-secret
YUKASSA_BASE_URL=https://api.yookassa.ru/v3
YUKASSA_WEBHOOK_IPS=127.0.0.1,payment-worker,payment-webhook
YUKASSA_FAKE_OUTCOME=success
```

Note that the prod `YUKASSA_BASE_URL` in the example is deliberate: it forces developers who flip to `live` to confront the safety rail (because creds are placeholders) rather than silently hitting prod.

## Atomicity Analysis (INV-004)

Unchanged from live behaviour. Webhook handler `_handle_payment_succeeded` / `_handle_payment_canceled` already wrap all DB writes in a single `session_scope`. The fake's contribution is *only* scheduling the webhook; the atomicity boundary is the webhook handler, which we do not touch.

## State Machine Impact (INV-016)

No transitions added or removed. Fake emits the same events consumed today.

## Risks / Trade-offs

- **[Risk]** Hostname resolution in `_is_whitelisted` could fail in non-compose environments (e.g. local pytest without Docker DNS) → **Mitigation:** resolution failures drop silently; tests that need the behaviour `monkeypatch.setattr("socket.gethostbyname", …)`.
- **[Risk]** Core-api reading `YUKASSA_BACKEND` via `os.getenv` bypasses Pydantic validation → **Mitigation:** health endpoint only reports the value for observability; any validation enforcement stays in payment-worker where the backend actually runs.
- **[Trade-off]** `docker-compose.override.yml` becoming a second source of truth → acceptable; it's dev-only and explicitly the Compose-recommended extension mechanism.

## Migration Plan

Forward-only; no schema changes. Deploy order:

1. Merge with default backend=live; existing prod `.env` unaffected.
2. Update dev `.env.example` to `fake`. Developers `cp .env.example .env` on pull.
3. Verify health endpoint reports the expected backend in each environment (staging, prod smoke test).
4. **Rollback:** revert the commit. No state to unwind.

## Open Questions

- Whether to add a CI rule refusing `YUKASSA_BACKEND=fake` in any `deploy/prod/**` file — follow-up change, not a blocker here.
