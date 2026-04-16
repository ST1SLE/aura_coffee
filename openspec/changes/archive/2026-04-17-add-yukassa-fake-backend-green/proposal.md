## Why

Implements the code to make all RED tests from change `add-yukassa-fake-backend-red` pass. Motivation, scope, and rationale are inherited verbatim from that change — in short: Phase 3 payments are untestable locally without real ЮKassa credentials and an external tunnel, and the webhook FastAPI app is defined but never served. Mirroring `SMS_BACKEND=log` with a `YUKASSA_BACKEND={live,fake}` toggle fixes both problems while keeping the live path untouched. References PDD §7.1, §8.1, INV-001, INV-004, INV-015, INV-016.

MVP phase: **Phase 3** (Order & Payment).

## What Changes

- Add `YUKASSA_BACKEND` (+`YUKASSA_FAKE_OUTCOME`) to `payment_worker.settings.Settings` with default `"live"` and a Pydantic validator.
- Add a boot-time safety rail refusing `live` mode with empty credentials or a non-production `base_url`.
- Introduce `services/payment-worker/src/payment_worker/yukassa_fake.py` — `FakeYukassaClient` returning deterministic payment/refund identifiers and scheduling a Celery callback that POSTs a canonical ЮKassa webhook to the in-cluster endpoint.
- Introduce `get_yukassa_client()` factory in `payment_worker.tasks`; refactor `create_payment` / `initiate_refund` to call the factory at task time.
- Extend `_is_whitelisted` in `payment_worker.webhook` to resolve Docker DNS hostnames (`payment-worker`, `payment-webhook`, …) while explicitly rejecting wildcards.
- Add `GET /health` to the payment-webhook FastAPI app; extend the existing core-api `/health` to include `yukassa_backend`.
- Deploy the webhook: add `payment-webhook` service to `docker-compose.yml` (+ a `docker-compose.override.yml` that maps port 8241 on the host for dev `curl`).
- Populate `.env.example` with the full `YUKASSA_*` block, dev defaults set to `fake`.
- Update `docs/phase3_manual_test_scenarios.md` preamble to remove the tunnel/sandbox-creds prerequisite.

## Capabilities

### New Capabilities
(none — the `payment-yukassa-backend` capability was introduced in the RED change's specs; this change does not add new requirements, only satisfies the existing ones)

### Modified Capabilities
(none — the RED spec already declares the target behaviour; GREEN is purely implementation to satisfy it)

## Impact

- **Code**: `services/payment-worker/src/payment_worker/{settings,tasks,webhook}.py`; new `yukassa_fake.py`; `services/core-api/src/core_api/routers/health.py` (or equivalent).
- **Infra**: `docker-compose.yml`, `docker-compose.override.yml` (new), `.env.example`.
- **Docs**: `docs/phase3_manual_test_scenarios.md` preamble.
- **Prod safety**: default stays `live`; safety rail refuses misconfigurations at boot; health endpoint exposes backend for smoke tests.
- **Out of scope**: changes to real `YukassaClient`, refund semantics, order lifecycle, or any frontend.

## Non-Goals

- No new requirements beyond what the RED change specifies.
- No gateway abstraction for non-ЮKassa providers.
- No UI-level E2E automation.
- No record/replay of real ЮKassa traffic.
