## 1. PREREQ — fixtures and test scaffolding

- [x] 1.1 [payment-worker] PREREQ: Add `YUKASSA_BACKEND`, `YUKASSA_FAKE_OUTCOME`, and an `autouse` settings-reset fixture to `services/payment-worker/tests/conftest.py` so each test starts from a clean env baseline. No assertions — infra only.

## 2. RED — Settings and backend toggle

- [x] 2.1 [payment-worker] RED: `services/payment-worker/tests/test_settings.py::test_yukassa_backend_defaults_to_live` — set none of the yukassa env, instantiate `Settings`, assert `s.yukassa_backend == "live"`. Fails today with `AttributeError: 'Settings' object has no attribute 'yukassa_backend'`.
- [x] 2.2 [payment-worker] RED: `services/payment-worker/tests/test_settings.py::test_yukassa_backend_accepts_fake` — `monkeypatch.setenv("YUKASSA_BACKEND", "fake")`, assert `s.yukassa_backend == "fake"`. Fails on same AttributeError.
- [x] 2.3 [payment-worker] RED: `services/payment-worker/tests/test_settings.py::test_yukassa_backend_rejects_unknown` — set `YUKASSA_BACKEND=mock`, assert `Settings()` raises `ValidationError`. Fails today (no validation).

## 3. RED — Safety rail (INV-015)

- [x] 3.1 [payment-worker] RED: `services/payment-worker/tests/test_settings_safety_rail.py::test_live_with_empty_shop_id_refused` — set backend=live, shop_id="", assert `ValidationError` referencing INV-015.
- [x] 3.2 [payment-worker] RED: `test_settings_safety_rail.py::test_live_with_empty_secret_refused` — live + empty secret → ValidationError.
- [x] 3.3 [payment-worker] RED: `test_settings_safety_rail.py::test_live_with_sandbox_url_refused` — live + base_url containing `sandbox` → ValidationError.
- [x] 3.4 [payment-worker] RED: `test_settings_safety_rail.py::test_live_with_test_url_refused` — live + base_url containing `test` → ValidationError.
- [x] 3.5 [payment-worker] RED: `test_settings_safety_rail.py::test_live_with_localhost_url_refused` — live + base_url containing `localhost` → ValidationError.
- [x] 3.6 [payment-worker] RED: `test_settings_safety_rail.py::test_fake_with_empty_creds_accepted` — backend=fake, empty creds → Settings() succeeds (rail bypassed).

## 4. RED — Factory function

- [x] 4.1 [payment-worker] RED: `services/payment-worker/tests/test_client_factory.py::test_factory_returns_live_client_by_default` — import `get_yukassa_client` from `payment_worker.tasks`, call it, assert `isinstance(client, YukassaClient)`. Fails with `ImportError` (no factory yet).
- [x] 4.2 [payment-worker] RED: `test_client_factory.py::test_factory_returns_fake_when_backend_fake` — monkeypatch backend=fake, assert returned object is `FakeYukassaClient`. Fails with ImportError on `payment_worker.yukassa_fake`.
- [x] 4.3 [payment-worker] RED: `test_client_factory.py::test_factory_is_called_per_task_not_at_import` — patch factory, enqueue `create_payment` twice, assert factory was called twice. Fails today because `tasks.py` builds client inline.

## 5. RED — FakeYukassaClient shape

- [x] 5.1 [payment-worker] RED: `services/payment-worker/tests/test_fake_client.py::test_create_payment_returns_fake_payment_id` — call `FakeYukassaClient().create_payment(...)`, assert `result["payment_id"]` matches `^fake_[0-9a-f]{32}$`.
- [x] 5.2 [payment-worker] RED: `test_fake_client.py::test_create_payment_confirmation_url_is_localhost` — assert `result["confirmation_url"].startswith("http://localhost:")` and contains `result["payment_id"]`.
- [x] 5.3 [payment-worker] RED: `test_fake_client.py::test_create_payment_status_pending` — assert `result["status"] == "pending"`.
- [x] 5.4 [payment-worker] RED: `test_fake_client.py::test_create_refund_returns_fake_refund_id` — assert refund id matches `^fake_refund_[0-9a-f]+$`.

## 6. RED — Fake self-drives webhooks

- [x] 6.1 [payment-worker] RED: `services/payment-worker/tests/test_fake_autodrive.py::test_create_payment_schedules_success_callback` — patch Celery `apply_async`, call `FakeYukassaClient().create_payment(...)` with `YUKASSA_FAKE_OUTCOME=success`, assert `apply_async` called once with task name `yukassa_fake_callback` and `countdown=1` and args containing `"payment.succeeded"`.
- [x] 6.2 [payment-worker] RED: `test_fake_autodrive.py::test_create_payment_schedules_cancel_callback` — same but outcome=canceled → callback args contain `"payment.canceled"`.
- [x] 6.3 [payment-worker] RED: `test_fake_autodrive.py::test_create_payment_http_error_outcome_raises` — outcome=http_error → `create_payment` raises `httpx.RequestError` synchronously and no callback is scheduled.
- [x] 6.4 [payment-worker] RED: `test_fake_autodrive.py::test_callback_posts_canonical_webhook_body` — invoke the callback task directly with a mocked `httpx.Client`, assert it POSTs to `http://payment-webhook:8241/webhooks/yukassa` with body shape `{"event": "payment.succeeded", "object": {"id": "fake_…", "status": "succeeded", "paid": true}}`.

## 7. RED — Webhook hostname whitelist

- [x] 7.1 [payment-worker] RED: `services/payment-worker/tests/test_webhook_whitelist.py::test_hostname_entry_resolves_and_matches` — monkeypatch `socket.gethostbyname` to return `172.20.0.5`, set `YUKASSA_WEBHOOK_IPS=payment-worker`, call `_is_whitelisted("172.20.0.5", settings.yukassa_webhook_ips)`, assert `True`.
- [x] 7.2 [payment-worker] RED: `test_webhook_whitelist.py::test_wildcard_is_not_permissive` — set whitelist `*`, call `_is_whitelisted("1.2.3.4", ...)`, assert `False`.
- [x] 7.3 [payment-worker] RED: `test_webhook_whitelist.py::test_localhost_default_accepted` — default `.env.example` whitelist (`127.0.0.1,payment-worker,payment-webhook`), call with `127.0.0.1`, assert `True`.

## 8. RED — Health endpoint exposes backend

- [x] 8.1 [payment-worker] RED: `services/payment-worker/tests/test_health.py::test_health_reports_backend_live` — FastAPI TestClient against `payment_worker.webhook.app` with backend=live (+ valid creds), `GET /health`, assert `200` and JSON `yukassa_backend=="live"`.
- [x] 8.2 [payment-worker] RED: `test_health.py::test_health_reports_backend_fake` — same with backend=fake, assert `yukassa_backend=="fake"`.
- [x] 8.3 [core-api] RED: `services/core-api/tests/test_health.py::test_health_includes_yukassa_backend` — GET `/health` on core-api app, assert response body contains `yukassa_backend` key.

## 9. RED — End-to-end fake drives order to PAID

- [x] 9.1 [payment-worker] RED: `services/payment-worker/tests/test_fake_e2e.py::test_fake_success_drives_order_to_paid` — use existing `seed_user_order_payment` + `fake_redis` + `sqlite_engine` fixtures + Celery eager mode. Call `create_payment.apply(...)`, synchronously run the scheduled callback, POST its body to `payment_worker.webhook.app` (TestClient), assert Order.status==PAID, Payment.status==SUCCEEDED, reservation converted to REDEMPTION.
- [x] 9.2 [payment-worker] RED: `test_fake_e2e.py::test_fake_canceled_drives_order_to_cancelled` — same with outcome=canceled, assert Order.status==CANCELLED, loyalty REVERSAL recorded, promocode.current_uses decremented.
- [x] 9.3 [payment-worker] RED: `test_fake_e2e.py::test_fake_http_error_triggers_compensation` — outcome=http_error, Celery eager with `throw=True`, assert 3 retries then `_fail_payment_and_cancel_order` runs: Payment=PAYMENT_FAILED, Order=CANCELLED, loyalty reversed.

## 10. VERIFY — All RED tests fail for the right reason

- [x] 10.1 [payment-worker] VERIFY: `docker compose run --rm payment-worker pytest services/payment-worker/tests/ -x` reports failures only from the new tests (ImportError / AttributeError / AssertionError), no collection errors on pre-existing test files. Capture the failing count into the GREEN change's starting delta.
