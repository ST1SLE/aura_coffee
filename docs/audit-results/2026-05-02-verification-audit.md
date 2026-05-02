# Verification, QA, Observability, and GRACE/LDD Audit

Date: 2026-05-02  
Scope: verification coverage, QA workflow, observability, LDD marker coverage,
manual-test docs, seed completeness, CI/release gates, dependency audit gates,
data reset strategy, Docker smoke checks, stale/flaky tests, and developer
workflow gaps.

This audit is read-only except for this report. Existing audit artifacts and
other agents' files were not edited.

## Executive Summary

Aura Coffee has broad unit/integration test coverage and a useful manual
clickthrough, but the verification system is not yet a release gate. The biggest
gap is that `docs/verification-plan.xml` requires GRACE/LDD assertions for
state transitions and atomic boundaries, while current marker assertions exist
only for the shared logger and one sms-worker OTP path. Core order creation,
payment webhook, and delivery-assignment markers are emitted in source, but not
asserted in tests.

The second release-level gap is automation: there is no tracked CI workflow,
no root verify script, no browser E2E suite, no Python dependency/security audit
gate, and no real readiness healthcheck for application services. Manual QA can
catch many issues, but it is too long and too stateful to protect routine
changes.

## Prioritized Findings

### P0 - Required LDD markers are emitted but mostly not asserted

`docs/verification-plan.xml` requires markers for:

- `CoreApi orders.create`: `BLOCK_TX_BEGIN`, `BLOCK_STATE_TRANSITION CREATED`
- `CoreApi auth.otp_request`: `BLOCK_OTP_GEN`
- `CoreApi auth.otp_verify`: `BLOCK_AUTH_VERIFY`
- `CoreApi delivery.assign/accept/deliver`: `BLOCK_STATE_TRANSITION`
- `CoreApi payment.webhook`: `BLOCK_WEBHOOK_VERIFY`
- `PaymentWorker process_webhook`: `BLOCK_TX_PAYMENT`, `BLOCK_STATE_TRANSITION PAID`
- `SmsWorker send_otp`: `BLOCK_SMSRU_CALL`

Source emits many of these markers:

- `services/core-api/src/core_api/services/checkout.py`
- `services/core-api/src/core_api/services/otp.py`
- `services/core-api/src/core_api/services/delivery_assignment.py`
- `services/core-api/src/core_api/services/order_lifecycle.py`
- `services/payment-worker/src/payment_worker/webhook.py`
- `services/sms-worker/src/sms_worker/tasks/otp.py`

But test assertion usage is sparse:

- `packages/shared/tests/test_grace_logging.py` tests the log helper itself.
- `services/sms-worker/tests/test_otp_task_log_backend.py` asserts
  `SmsWorker/send_otp/BLOCK_SMSRU_CALL` and redaction.
- No `services/core-api/tests/*.py` currently uses `grace_logs` outside
  `conftest.py`.
- No `services/payment-worker/tests/*.py` currently uses `GraceLogCapture` or
  `assert_trajectory`.

Impact: normal tests can pass while required transaction/state-machine
observability silently regresses.

Recommended fixes:

- Add LDD assertion tests for checkout order creation:
  `orders.create -> BLOCK_TX_BEGIN -> BLOCK_STATE_TRANSITION -> BLOCK_TX_COMMIT`,
  and assert no `BLOCK_TX_COMMIT` on failed atomic checkout.
- Add LDD assertion tests for delivery assignment transitions:
  assign, accept, pickup/deliver, and cancel/closed paths.
- Add LDD assertion tests for payment webhook happy and failure paths:
  `BLOCK_WEBHOOK_VERIFY` before DB mutation, then `BLOCK_TX_PAYMENT` and
  state belief lines.
- Add OTP verify assertion coverage for `BLOCK_AUTH_VERIFY` and redaction.

### P0 - There is no tracked CI/release verification gate

Evidence:

- `find .github/workflows -type f` found zero workflow files.
- No root `Makefile`, `justfile`, `Taskfile.yml`, `tox.ini`, `noxfile.py`,
  `pre-commit`, Dependabot, Renovate, or codecov config was found.
- Verification commands are spread across `AGENTS.md`,
  `docs/verification-plan.xml`, package scripts, and manual docs.

Impact: the project relies on humans/agents remembering which checks matter.
This is already visible in stale audit logs and in the gap between LDD policy
and actual LDD assertions.

Recommended fixes:

- Add `scripts/verify-fast.sh` for local pre-commit-ish checks:
  frontend lint, targeted backend ruff, route/RBAC tests, LDD smoke tests.
- Add `scripts/verify-full.sh` for containerized full suite:
  migrations, core-api pytest, payment-worker pytest, sms-worker pytest,
  shared pytest, both Vitest suites, npm audit, Python audit.
- Add GitHub Actions or equivalent CI with the same commands.
- Make CI fail if required package scripts are missing.

### P0 - Browser E2E coverage is absent

Evidence:

- No Playwright/Cypress config or real browser E2E suite is tracked.
- Existing `e2e` hits are old audit logs plus
  `services/payment-worker/tests/test_fake_e2e.py`, which is backend-only.
- `docs/phase6_manual_test_scenarios.md` is comprehensive but manual and
  stateful.

Impact: the riskiest regressions for this product are cross-role UI flows:
customer checkout, barista order transitions, courier assignment, admin promo
CRUD, auth/logout role switching. Vitest covers components/API clients, but it
does not prove the browser and running stack together.

Recommended fixes:

- Add Playwright with a seeded, isolated Compose project.
- First E2E smoke should be small and deterministic:
  customer login via Redis OTP -> add menu item -> create pickup order ->
  fake payment -> barista marks preparing/ready/completed.
- Add second E2E for delivery:
  seeded delivery order -> barista ready -> courier take/pickup/deliver.
- Add role-switch E2E:
  admin logout -> barista login -> forbidden admin pages redirect.

### P1 - Core/shared/database ruff gate currently fails

Current command:

```bash
docker compose exec -T core-api ruff check services/core-api/src database packages/shared/src
```

Result: failed with 12 errors. Main categories:

- `F821` unresolved forward-reference names in shared models:
  `User`, `UserProfile`, `LoyaltyAccount`.
- `F401` unused import in `routers/admin_promocodes.py`.
- `F841` unused locals in `routers/auth.py`, `routers/orders.py`,
  `services/cart.py`.
- `E402` module imports below runtime code in `services/checkout.py`.

Payment and SMS runtime source checks passed:

```bash
docker compose exec -T payment-worker ruff check services/payment-worker/src
docker compose exec -T sms-worker ruff check services/sms-worker/src
```

Impact: a real release gate would currently fail before tests.

Recommended fix: fix runtime lint first, then decide whether tests/migrations
are included in the standard ruff gate or have a narrower rule set.

### P1 - Verification plan and package scripts drift

`docs/verification-plan.xml` says both frontends should support:

```bash
npm run typecheck
```

But `web/customer/package.json` and `web/admin/package.json` do not define a
`typecheck` script. They have `build`, which runs `tsc -b && vite build`, but
build can update `tsconfig.tsbuildinfo` and is heavier than a typecheck gate.

Recommended fixes:

- Add `typecheck` scripts to both frontend packages, likely `tsc -b --pretty false`.
- Consider moving `tsBuildInfoFile` into an ignored cache path, or do not track
  `tsconfig.tsbuildinfo`.
- Update `docs/verification-plan.xml` only after the scripts exist and are run
  by CI.

### P1 - Manual guide has stale log-redaction instructions

`docs/phase6_manual_test_scenarios.md` says the SMS log backend echoes raw phone
and OTP body:

```text
[SMS:log] to=+79991234567 msg=...
```

Current code intentionally logs redacted metadata:

```text
[SMS:log] recipient_ref=<hash-prefix> kind=otp message_len=<n>
```

Current tests assert the raw phone, OTP code, and SMS body are absent from logs.

Impact: the manual guide asks testers to expect a behavior that would violate
INV-013 if it actually happened. It can also cause false debugging when testers
look for OTP in logs instead of Redis.

Recommended fix: update the manual guide to show the redacted log line and make
Redis the only local OTP retrieval path.

### P1 - Application health checks are liveness-only, not readiness

Current smoke:

```bash
curl http://localhost:$CORE_API_PORT/health
curl http://localhost:$PAYMENT_WEBHOOK_PORT/health
curl -o /dev/null -w '%{http_code}' http://localhost:$NGINX_PORT/
```

Results: all returned OK/200 in the current stack.

Gaps:

- `core-api /health` reads only `YUKASSA_BACKEND`; it does not check DB, Redis,
  migrations, Celery dispatch, or worker availability.
- `payment-webhook /health` is also lightweight.
- Compose healthchecks exist for Postgres and Redis only. `core-api`,
  `payment-webhook`, `payment-worker`, `sms-worker`, `web-customer`,
  `web-admin`, and `nginx` are only `Up`, not healthchecked.
- `scripts/up.sh` waits for container state, but cannot prove the app is ready.

Recommended fixes:

- Add `/ready` to core-api that checks DB connection and Redis.
- Add Compose healthchecks for core-api, payment-webhook, nginx, and the two
  Vite services.
- Add worker smoke command using Celery inspect or a lightweight task ping.
- Add a post-up smoke script that fails if API, frontends, or workers are not
  actually reachable.

### P1 - Dependency/security audit gates are partial

Current checks run during this audit:

```bash
cd web/customer && npm audit --json
cd web/admin && npm audit --json
```

Both returned zero npm vulnerabilities at the time of this run.

Gaps:

- `pip-audit`, `safety`, and `bandit` are not installed on the host.
- No Python dependency audit command is documented as a gate.
- Only `services/core-api/uv.lock` exists; payment-worker, sms-worker, and
  shared install from open ranges in `pyproject.toml` via `pip install -e`.
- Dockerfiles install unconstrained dependencies and do not use a lock file.

Recommended fixes:

- Pick one Python dependency strategy: per-service `uv.lock` or a workspace lock.
- Add `pip-audit` or `uv pip audit` equivalent once the lock strategy is settled.
- Add `bandit` or another security linter for Python source, tuned to avoid
  noise in tests/migrations.
- Add Dependabot/Renovate for npm and Python.

### P2 - Data reset strategy is useful but too coarse for safe QA loops

Current strengths:

- `database/seeds/phase4_manual_test.py` is idempotent and now covers staff,
  multiple customers, addresses, loyalty, menu variants, media URL fields,
  promocodes, orders, payments, assignments, refunds, and notifications.
- Core-api tests have a Postgres test DB path with outer transaction rollback.
- Payment-worker tests use isolated SQLite and table cleanup.

Gaps:

- Manual docs still advertise `docker compose down -v` as the full reset path.
  That is correct when intentionally wiping a dev stack, but too destructive as
  the default QA reset muscle memory.
- There is no dedicated non-destructive `reset-qa-data` script that wipes only
  deterministic QA rows and re-runs the manual seed.
- The seed stores media paths but does not create media files; visual media
  testing still depends on optional local files.
- Yandex Maps remains real-only locally, so fresh typed-address delivery flows
  cannot be fully deterministic without a valid external key.

Recommended fixes:

- Add a `scripts/reset-qa-data.sh` that refuses to run unless `APP_ENV=local`
  or an explicit `ALLOW_QA_RESET=1` is present.
- Keep `down -v` in docs, but label it as destructive and not part of routine QA.
- Add generated placeholder media fixtures that are approved for commit, or a
  script that creates them under `web/customer/public/media/...`.
- Add a fake Yandex provider mode or a deterministic test-only geocode fixture.

### P2 - Stale/flaky-test signal is not curated

Prior audit logs under `docs/audit-results/` show an old full core-api run with
22 failures and old npm audit vulnerability messages. Current targeted reruns
show several of those failures are stale:

```bash
docker compose exec -T core-api pytest \
  services/core-api/tests/test_route_cart.py::test_post_cart_item_merges_same_line \
  services/core-api/tests/test_route_cart.py::test_patch_cart_item_updates_quantity \
  services/core-api/tests/test_route_cart.py::test_delete_cart_item_removes_line \
  services/core-api/tests/test_route_cart.py::test_cart_ttl_env_override_respected -q
# 4 passed

docker compose exec -T core-api pytest \
  services/core-api/tests/test_delivery_assignment_state_machine.py::test_list_available_for_courier_returns_only_awaiting \
  services/core-api/tests/test_menu_public.py::test_get_menu_empty_database_returns_empty_list \
  services/core-api/tests/test_schemas_order.py::test_shop_settings_response_round_trip -q
# 3 passed
```

Recurring warning classes remain worth cleaning:

- PyJWT `InsecureKeyLengthWarning` in tests using short secrets.
- React `act(...)` warnings in Vitest output.
- Radix Dialog accessibility warnings about missing descriptions.

Recommended fixes:

- Add a dated test-status summary that distinguishes current failures from
  historical audit logs.
- Normalize test JWT secrets to at least 32 bytes.
- Clean React act warnings and Dialog aria warnings; then fail CI on new stderr
  warnings for frontend tests.

## Current Positive Coverage

- Test inventory is broad:
  - 105 Python test files under `services`, `packages`, and `database`.
  - 45 admin Vitest files.
  - 33 customer Vitest files.
- Frontend lint passed for both apps:
  - `cd web/customer && npm run lint`
  - `cd web/admin && npm run lint`
- Npm audit passed for both apps at this point in time:
  - `cd web/customer && npm audit --json`
  - `cd web/admin && npm audit --json`
- Current targeted backend tests passed:
  - RBAC route coverage and RBAC matrix: 14 passed.
  - sms-worker OTP LDD/redaction test: 1 passed.
  - payment-worker webhook happy path: 1 passed.
  - selected stale core-api failures: 7 passed.
- Current stack is up and reachable:
  - `core-api /health`: `{"status":"ok","yukassa_backend":"fake"}`
  - nginx root: 200
  - `payment-webhook /health`: `{"status":"ok","yukassa_backend":"fake"}`
- Celery registered task inspection currently includes:
  - `sms_worker.send_order_notification_sms`
  - `sms_worker.tasks.otp.send_otp_sms`
  - `payment_worker.tasks.create_payment`
  - `payment_worker.tasks.initiate_refund`
  - `yukassa_fake_callback`
  - `pickup.close_stale`

## Proposed Verification Roadmap

### Phase 0 - Codify the local gates

Deliverables:

- `scripts/verify-fast.sh`
- `scripts/verify-full.sh`
- CI workflow that invokes the same scripts

Minimum fast gate:

```bash
docker compose exec -T core-api ruff check services/core-api/src database packages/shared/src
docker compose exec -T payment-worker ruff check services/payment-worker/src
docker compose exec -T sms-worker ruff check services/sms-worker/src
cd web/customer && npm run lint
cd web/admin && npm run lint
docker compose exec -T core-api pytest services/core-api/tests/test_route_coverage.py services/core-api/tests/test_rbac_matrix.py -q
docker compose exec -T sms-worker pytest services/sms-worker/tests/test_otp_task_log_backend.py::test_send_otp_sms_emits_ldd_marker_and_redacts_logs -q
```

### Phase 1 - Close the LDD assertion gap

Deliverables:

- Core-api LDD tests for checkout, OTP verify, delivery assignment, order status
  transitions, and cancellation.
- Payment-worker LDD tests for webhook success, webhook rejection, and failure
  compensation.
- Redaction tests for auth/SMS/payment webhook paths.

Required assertion style:

- `grace_logs.assert_trajectory(...)`
- `assert grace_logs.beliefs(status="MISMATCH") == []`
- redaction assertions for phone, OTP code, JWT, password, API key, raw webhook
  body, and full address where relevant.

### Phase 2 - Add browser E2E smoke

Deliverables:

- Playwright config.
- Seed/bootstrap helper that uses a unique Compose project or current stack.
- Four smoke specs:
  - customer login/menu/cart/pickup checkout
  - barista order transitions
  - courier assignment delivery
  - admin logout -> barista login -> role-restricted navigation

### Phase 3 - Add readiness and operational smoke

Deliverables:

- `/ready` endpoint for core-api.
- Compose healthchecks for application services.
- `scripts/smoke-stack.sh` checking:
  - nginx routes both SPAs
  - core-api health/readiness
  - payment-webhook health
  - Celery registered tasks
  - public menu and seeded admin login

### Phase 4 - Add dependency and security gates

Deliverables:

- Python lock strategy for all Python services.
- Python dependency audit command.
- npm audit in CI.
- security linter for Python with tuned exclusions.
- Renovate/Dependabot.

### Phase 5 - Stabilize QA reset and manual docs

Deliverables:

- Non-destructive QA data reset script with environment guard.
- Manual guide update for SMS log redaction.
- Manual guide update for current logout/role-switch workflow.
- Optional committed QA media fixtures or media fixture generator.
- Optional fake Yandex mode for deterministic delivery-address testing.

## Future Fixes That Require LDD Assertions

LDD assertions are required for any future fix touching:

- `orders.create`, checkout pricing, cart-to-order conversion, points, promo,
  payment creation, or rollback behavior.
- Order status transitions, customer/admin cancellation, pickup auto-close, or
  delivery assignment transitions.
- Payment webhook verification, payment/refund state changes, webhook
  idempotency, or payment-worker compensation paths.
- Customer OTP send/verify, staff auth, JWT refresh/logout, RBAC middleware,
  blocked/deleted customer handling, or any auth/role check.
- SMS worker log transport, SMS.ru transport, notification tasks, or any path
  that can log phone, OTP, message body, token, API key, webhook body, or full
  address.
- Any change to a marker listed in `docs/verification-plan.xml`.

LDD assertions are normally not required for:

- Pure frontend styling with no auth/session/role behavior.
- Documentation-only fixes.
- CI script additions that only orchestrate existing commands.
- Package script additions, unless they change runtime auth/PII/logging paths.

## Commands Run

```bash
git status --short
find docs/audit-results -maxdepth 1 -type f -printf '%f\n' | sort
find .github -maxdepth 3 -type f -print
rg -n "grace_logs|GraceLogCapture|assert_trajectory|beliefs\(" services packages --glob '*test*.py'
rg -n "BLOCK_AUTH_VERIFY|BLOCK_TX_BEGIN|BLOCK_STATE_TRANSITION|BLOCK_WEBHOOK_VERIFY|BLOCK_TX_PAYMENT|BLOCK_SMSRU_CALL|BLOCK_OTP_GEN|BLOCK_TX_COMMIT|BLOCK_YUKASSA_CALL" services packages
docker compose ps --format json
cd web/customer && npm audit --json
cd web/admin && npm audit --json
cd web/customer && npm run lint
cd web/admin && npm run lint
docker compose exec -T core-api pytest services/core-api/tests/test_route_coverage.py services/core-api/tests/test_rbac_matrix.py -q
docker compose exec -T sms-worker pytest services/sms-worker/tests/test_otp_task_log_backend.py::test_send_otp_sms_emits_ldd_marker_and_redacts_logs -q
docker compose exec -T payment-worker pytest services/payment-worker/tests/test_webhook.py::test_payment_succeeded_advances_payment_and_order -q
docker compose exec -T core-api pytest services/core-api/tests/test_route_cart.py::test_post_cart_item_merges_same_line services/core-api/tests/test_route_cart.py::test_patch_cart_item_updates_quantity services/core-api/tests/test_route_cart.py::test_delete_cart_item_removes_line services/core-api/tests/test_route_cart.py::test_cart_ttl_env_override_respected -q
docker compose exec -T core-api pytest services/core-api/tests/test_delivery_assignment_state_machine.py::test_list_available_for_courier_returns_only_awaiting services/core-api/tests/test_menu_public.py::test_get_menu_empty_database_returns_empty_list services/core-api/tests/test_schemas_order.py::test_shop_settings_response_round_trip -q
docker compose exec -T core-api ruff check services/core-api/src database packages/shared/src
docker compose exec -T payment-worker ruff check services/payment-worker/src
docker compose exec -T sms-worker ruff check services/sms-worker/src
docker compose exec -T sms-worker celery -A sms_worker.main:celery_app inspect registered
docker compose exec -T payment-worker celery -A payment_worker.main:celery_app inspect registered
```

No destructive commands were run. No secrets were printed in this report.
