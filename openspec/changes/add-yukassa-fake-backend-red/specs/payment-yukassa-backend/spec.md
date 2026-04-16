## ADDED Requirements

### Requirement: Pluggable ЮKassa transport backend

The payment-worker SHALL select its ЮKassa transport at runtime from an `YUKASSA_BACKEND` environment variable of type `Literal["live", "fake"]`, defaulting to `"live"` in code. References PDD §8.1, INV-015.

#### Scenario: Live backend is default in code
- **WHEN** the payment-worker process starts with no `YUKASSA_BACKEND` env var set
- **THEN** `settings.yukassa_backend` resolves to `"live"` and `get_yukassa_client()` returns the real `YukassaClient` that performs HTTPS calls to `settings.yukassa_base_url`

#### Scenario: Fake backend opt-in via env
- **WHEN** `YUKASSA_BACKEND=fake` is exported before starting payment-worker
- **THEN** `get_yukassa_client()` returns a `FakeYukassaClient` instance and no HTTPS call is issued for `create_payment` or `create_refund`

#### Scenario: Invalid backend value refused at boot
- **WHEN** `YUKASSA_BACKEND=mock` (or any value not in `{live, fake}`) is set
- **THEN** the process fails to start with a Pydantic validation error naming the field and its allowed values

### Requirement: Fake client returns deterministic payment identifiers

`FakeYukassaClient.create_payment()` SHALL return a response shape identical to the live client's return contract, with `payment_id` prefixed `fake_` and a `confirmation_url` pointing to a local dev host.

#### Scenario: create_payment response shape
- **WHEN** `FakeYukassaClient.create_payment(amount_kopecks=30000, idempotency_key="k1", return_url="…", description="…")` is called
- **THEN** the returned dict contains keys `payment_id`, `confirmation_url`, `status`, `payment_id` matches `^fake_[0-9a-f]{32}$`, `confirmation_url` starts with `http://localhost:` and contains the `payment_id`, and `status == "pending"`

#### Scenario: create_refund response shape
- **WHEN** `FakeYukassaClient.create_refund(payment_id="fake_…", amount_kopecks=30000, idempotency_key="r1")` is called
- **THEN** the returned dict contains a refund id prefixed `fake_refund_` and mirrors the live client's refund response structure

### Requirement: Fake client self-drives webhooks via Celery

`FakeYukassaClient.create_payment()` SHALL enqueue a Celery task with a 1-second countdown that POSTs a canonical ЮKassa webhook body to the local webhook endpoint. The posted event MUST be consumable by the existing `payment_worker.webhook.dispatch_event` without modification (INV-016).

#### Scenario: Successful payment auto-drives to PAID
- **WHEN** an order is created with `total > 0` and payment-worker is running with `YUKASSA_BACKEND=fake` and `YUKASSA_FAKE_OUTCOME=success`
- **THEN** within 5 seconds the order's `status` transitions `CREATED → PAID`, the associated Payment row has `status=SUCCEEDED`, and the customer's Redis cart key is deleted — without any external HTTP traffic leaving the Docker network

#### Scenario: Canceled outcome auto-drives to CANCELLED
- **WHEN** an order is created with `YUKASSA_FAKE_OUTCOME=canceled`
- **THEN** within 5 seconds the order's `status` becomes `CANCELLED`, the Payment's `status` becomes `PAYMENT_FAILED`, loyalty reservation is reversed, and any promocode `current_uses` is decremented (INV-004)

#### Scenario: HTTP error outcome triggers compensation
- **WHEN** an order is created with `YUKASSA_FAKE_OUTCOME=http_error`
- **THEN** `FakeYukassaClient.create_payment` raises `httpx.RequestError`, Celery retries according to the existing `autoretry_for` policy, and after `max_retries` the `_fail_payment_and_cancel_order` compensation runs — leaving Payment=PAYMENT_FAILED, Order=CANCELLED, loyalty reversed, promocode decremented (INV-004)

### Requirement: Webhook endpoint served in the dev stack

`docker-compose.yml` SHALL run a `payment-webhook` service executing `uvicorn payment_worker.webhook:app --host 0.0.0.0 --port 8241`, reachable from the `payment-worker` service over the Docker network. `docker-compose.override.yml` SHALL expose port 8241 on the host for manual simulation.

#### Scenario: In-cluster webhook reachable from fake
- **WHEN** payment-worker (fake backend) schedules its self-driven webhook
- **THEN** the Celery task reaches `http://payment-webhook:8241/webhooks/yukassa` and receives HTTP 200 on first delivery attempt

#### Scenario: Host-exposed webhook supports manual simulation
- **WHEN** a developer runs `./scripts/up.sh` (which loads `docker-compose.override.yml`) and issues `curl -X POST http://localhost:8241/webhooks/yukassa …` from the host with a valid canonical body
- **THEN** the request is accepted (not connection-refused) and processed according to the event type

### Requirement: IP whitelist resolves in-cluster hostnames

`_is_whitelisted` SHALL accept entries that are DNS names resolvable on the Docker network (e.g. `payment-worker`, `payment-webhook`) in addition to IPs and CIDRs. Wildcard `*` SHALL NOT be supported.

#### Scenario: Hostname entry matches container IP
- **WHEN** `YUKASSA_WEBHOOK_IPS=payment-worker` and the fake task POSTs from the payment-worker container
- **THEN** the webhook handler accepts the request with HTTP 200

#### Scenario: Wildcard entry rejected
- **WHEN** `YUKASSA_WEBHOOK_IPS=*` and any request arrives
- **THEN** the whitelist returns False and the endpoint responds HTTP 403

#### Scenario: Localhost works by default
- **WHEN** `.env` is a fresh copy of `.env.example` (which includes `127.0.0.1` in `YUKASSA_WEBHOOK_IPS`) and a developer curls from the host
- **THEN** the request is accepted

### Requirement: Boot-time safety rail for live backend

`Settings` SHALL refuse to instantiate when `yukassa_backend == "live"` and any of the following hold: `yukassa_shop_id` is empty, `yukassa_secret_key` is empty, or `yukassa_base_url` (case-insensitively) contains any of `test`, `sandbox`, `localhost`, `127.0.0.1`. References INV-015. Mirrors the existing SMS backend safety rail at `services/sms-worker/src/sms_worker/settings.py`.

#### Scenario: Empty credentials refused in live mode
- **WHEN** the process starts with `YUKASSA_BACKEND=live`, `YUKASSA_SHOP_ID=""`, `YUKASSA_SECRET_KEY=""`
- **THEN** `Settings()` raises `ValidationError` referencing INV-015; the process exits non-zero before any task or HTTP server starts

#### Scenario: Non-production base URL refused in live mode
- **WHEN** the process starts with `YUKASSA_BACKEND=live`, credentials present, and `YUKASSA_BASE_URL=https://api.sandbox.yookassa.ru/v3`
- **THEN** `Settings()` raises `ValidationError` naming the offending substring

#### Scenario: Fake mode bypasses the rail
- **WHEN** the process starts with `YUKASSA_BACKEND=fake` and empty credentials
- **THEN** `Settings()` instantiates successfully; empty credentials are acceptable because the fake does not use them

### Requirement: Health endpoint exposes backend selection

Both `payment-webhook` and `core-api` SHALL expose `GET /health` returning at minimum `{"yukassa_backend": "live"|"fake"}`. This enables deploy smoke tests to assert production is not running a fake transport.

#### Scenario: Health reports live in production-shaped config
- **WHEN** the process runs with `YUKASSA_BACKEND=live` and valid credentials
- **THEN** `GET /health` returns HTTP 200 with a JSON body where `yukassa_backend == "live"`

#### Scenario: Health reports fake in dev-shaped config
- **WHEN** the process runs with `YUKASSA_BACKEND=fake`
- **THEN** `GET /health` returns HTTP 200 with `yukassa_backend == "fake"`

### Requirement: Environment example ships dev-safe defaults

`.env.example` SHALL declare `YUKASSA_BACKEND=fake`, placeholder shop_id/secret_key, the production `YUKASSA_BASE_URL` (ignored in fake mode but realistic if the developer flips to live), `YUKASSA_WEBHOOK_IPS=127.0.0.1,payment-worker,payment-webhook`, and `YUKASSA_FAKE_OUTCOME=success`. A fresh `cp .env.example .env` SHALL produce a stack where the full Phase 3 lifecycle is testable with zero additional configuration.

#### Scenario: Fresh clone runs full lifecycle
- **WHEN** a developer clones the repo, runs `cp .env.example .env`, and runs `./scripts/up.sh`
- **THEN** placing an order via the customer UI drives the order to `status=PAID` within 5 seconds without any credential provisioning, tunnel setup, or ЮKassa account
