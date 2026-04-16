## 1. GREEN — Settings toggle and safety rail

- [ ] 1.1 [payment-worker] GREEN: Add `yukassa_backend: Literal["live","fake"] = "live"` and `yukassa_fake_outcome: Literal["success","canceled","http_error"] = "success"` to `Settings` in `services/payment-worker/src/payment_worker/settings.py` → passes 2.1, 2.2, 2.3.
- [ ] 1.2 [payment-worker] GREEN: Add `@model_validator(mode="after")` `_check_live_mode_safety` to `Settings` enforcing non-empty creds + no `test|sandbox|localhost|127.0.0.1` substring in `yukassa_base_url` when backend=live → passes 3.1–3.6.

## 2. GREEN — Factory

- [ ] 2.1 [payment-worker] GREEN: Add `get_yukassa_client()` factory to `services/payment-worker/src/payment_worker/tasks.py` branching on `settings.yukassa_backend`; import `FakeYukassaClient` lazily inside the branch → passes 4.1, 4.2.
- [ ] 2.2 [payment-worker] REFACTOR: Replace direct `YukassaClient(...)` construction in `create_payment` and `initiate_refund` (`tasks.py:129-133`, `tasks.py:185-189`) with `get_yukassa_client()` — behaviour-preserving → passes 4.3.

## 3. GREEN — FakeYukassaClient module

- [ ] 3.1 [payment-worker] GREEN: Create `services/payment-worker/src/payment_worker/yukassa_fake.py` with `FakeYukassaClient.create_payment/get_payment/create_refund` returning the deterministic shapes → passes 5.1–5.4.
- [ ] 3.2 [payment-worker] GREEN: In the same module add the `@celery_app.task(name="yukassa_fake_callback", max_retries=0)` that POSTs canonical webhook bodies to `http://payment-webhook:8241/webhooks/yukassa` → passes 6.4 and the "non-retrying contract" scenarios.
- [ ] 3.3 [payment-worker] GREEN: Wire outcome dispatch inside `FakeYukassaClient.create_payment` — `success`/`canceled` schedule the callback with `countdown=1`, `http_error` raises `httpx.RequestError` synchronously → passes 6.1, 6.2, 6.3.

## 4. GREEN — Webhook hostname whitelist

- [ ] 4.1 [payment-worker] GREEN: Extend `_is_whitelisted` in `services/payment-worker/src/payment_worker/webhook.py` to resolve non-IP/CIDR entries via `socket.gethostbyname` with a module-level cache; explicitly treat `*` as non-match → passes 7.1, 7.2, 7.3.

## 5. GREEN — Health endpoints

- [ ] 5.1 [payment-worker] GREEN: Add `@app.get("/health")` to `payment_worker.webhook` returning `{"status":"ok","yukassa_backend": settings.yukassa_backend}` → passes 8.1, 8.2.
- [ ] 5.2 [core-api] GREEN: Extend core-api's existing `/health` route to include `yukassa_backend` via `os.getenv("YUKASSA_BACKEND", "live")`, no `payment_worker` import → passes 8.3 and the "no payment_worker import" scenario.

## 6. PREREQ — Infrastructure wiring

- [ ] 6.1 [infra] PREREQ: Add `payment-webhook` service block to `docker-compose.yml` — same build context as `payment-worker`, `command: ["uvicorn","payment_worker.webhook:app","--host","0.0.0.0","--port","8241"]`, depends on postgres + redis, no host port mapping.
- [ ] 6.2 [infra] PREREQ: Create `docker-compose.override.yml` at repo root mapping `"8241:8241"` on `payment-webhook` for dev-only host access.
- [ ] 6.3 [infra] PREREQ: Append the full `YUKASSA_*` block to `.env.example` with dev defaults per design.md D6.

## 7. VERIFY — Full RED suite passes

- [ ] 7.1 [payment-worker] VERIFY: `docker compose run --rm payment-worker pytest services/payment-worker/tests/ -x` reports 0 failures, collects every test added in the RED change.
- [ ] 7.2 [payment-worker] VERIFY: `./scripts/up.sh` on a freshly `cp .env.example .env` clone, place a `total>0` order via the customer UI, poll the order detail; order reaches `status=PAID` within 10s. Record the observed latency.
- [ ] 7.3 [payment-worker] VERIFY: `curl http://localhost:8241/webhooks/yukassa -H 'Content-Type: application/json' -d '{"event":"payment.succeeded","object":{"id":"fake_…","status":"succeeded","paid":true}}'` (against a paid fake payment id) returns HTTP 200.
- [ ] 7.4 [core-api] VERIFY: `curl http://localhost:${NGINX_PORT}/api/v1/health` (or core-api direct) returns JSON including `yukassa_backend` key.
- [ ] 7.5 [payment-worker] VERIFY: Flip `.env` to `YUKASSA_BACKEND=live` with empty secrets; `docker compose restart payment-worker`; container exits non-zero with a ValidationError in logs. Restore afterwards.

## 8. REFACTOR — Documentation

- [ ] 8.1 [infra] REFACTOR: Update `docs/phase3_manual_test_scenarios.md` preamble — remove tunnel/sandbox-creds prerequisite; note that Block 4.2 now completes autonomously within ~2s with `YUKASSA_BACKEND=fake`; keep the real-sandbox path as an opt-in alternative.
