# Aura Coffee Autonomous Test Audit

Date: 2026-04-30
Workspace: `/tmp/aura-coffee-audit-20260430-111515`
Compose project: `aura_audit_111515`

## Safety Setup

- Work ran in a copied `/tmp` workspace, not the original repo.
- Real `.env`, `.git`, `.venv`, `node_modules`, and caches were excluded from the copy.
- Externals were sandboxed/mocked: `YUKASSA_BACKEND=fake`, `SMS_BACKEND=log`, empty `YANDEX_MAPS_API_KEY`.
- Runtime database/Redis were isolated under the compose project `aura_audit_111515`.
- Actual observed host ports: core API `8180`, nginx `8260`, customer `5353`, admin `5354`, postgres `5613`, redis `6559`.
- Reusable setup notes were saved to `/home/p3tal/.codex/memories/aura-coffee-safe-audit.md`.

## Executive Status

The main happy path works end-to-end in the isolated stack: staff login, customer OTP, menu, cart, checkout, fake payment, pickup order state transitions, delivery order state transitions, and courier assignment all completed successfully.

The project is not release-clean yet. The biggest blockers are:

1. Customer frontend production build fails on TypeScript unused imports.
2. Live order-status SMS tasks are discarded by the running SMS worker as unregistered tasks.
3. SMS log transport writes raw phone numbers and OTP codes to logs, conflicting with INV-013.
4. Core API test suite is not green; several failures are stale tests or harness drift, but CI would still fail.
5. Python lint is noisy: `ruff check .` reports 73 errors.
6. Both frontend apps have one moderate `postcss` npm advisory.

## Verification Matrix

| Area | Result | Evidence |
| --- | --- | --- |
| Docker stack startup | PASS | `audit-results/stack-ps.log`, current `docker compose ps` |
| Core API health | PASS | `audit-results/health-core.log` |
| Shared pytest | PASS, 11/11 | `audit-results/shared-pytest.log` |
| Payment worker pytest | PASS, 54/54 | `audit-results/payment-worker-pytest.log` |
| SMS worker pytest | PASS, 19/19 | `audit-results/sms-worker-pytest.log` |
| Core API pytest | FAIL, 10 failed / 1084 passed / 1 skipped | `audit-results/core-api-pytest-freshdb-testsecret.log` |
| Customer Vitest | PASS, 170/170, warnings | `audit-results/customer-vitest.log` |
| Admin Vitest | PASS, 270/270, warnings | `audit-results/admin-vitest.log` |
| Customer build | FAIL | `audit-results/customer-build.log` |
| Admin build | PASS, chunk warning | `audit-results/admin-build.log` |
| Customer ESLint | FAIL, 3 errors / 3 warnings | `audit-results/customer-eslint.log` |
| Admin ESLint | PASS | `audit-results/admin-eslint.log` |
| Ruff | FAIL, 73 errors | `audit-results/ruff-all.log` |
| npm audit customer/admin | FAIL, 1 moderate each | `audit-results/npm-audit-*.log` |
| Live API/manual E2E | PASS, with SMS-task errors in logs | `audit-results/manual-e2e-flow.log` |
| Targeted live cart/admin probes | PASS | `audit-results/live-targeted-probes.log` |
| Secret-pattern scan | No live private keys found; placeholders/dev env detected | `audit-results/secret-pattern-scan.log` |

## What Works

- Stack boots with Postgres, Redis, core API, workers, frontends, payment webhook, and nginx.
- Migrations apply cleanly on fresh isolated DB.
- Staff authentication works for admin, barista, and courier.
- Customer OTP send/verify works in log mode.
- Public menu returns seeded QA menu.
- Cart works live when the same customer token is reused:
  - add duplicate line merged to quantity `4`
  - patch quantity returned `200`
  - delete line returned `200`
- Pickup checkout works:
  - checkout creates order
  - fake payment advances to `paid`
  - staff transitions `preparing -> ready -> completed`
- Delivery checkout works:
  - checkout creates order
  - fake payment advances to `paid`
  - staff transitions `preparing -> ready`
  - courier available list returns one assignment
  - courier take/pickup/deliver advances assignment to `delivered`
- Payment worker fake backend and webhook behavior have strong test coverage and pass.
- SMS worker unit tests pass, including retry/status behavior for notification task when the module is directly imported.
- Admin frontend tests/build/lint pass, aside from build-size and test-console warnings.

## High-Priority Findings

### 1. Customer Frontend Cannot Build

`npm run build` in `web/customer` fails on TypeScript unused imports:

- `src/App.test.tsx`: unused `AuthProvider`
- `src/pages/VerifyPage.test.tsx`: unused `beforeEach`, `afterEach`

Customer ESLint reports the same three errors, plus hook dependency warnings in:

- `src/pages/Cart/CartPage.tsx`
- `src/pages/Profile/Addresses/AddressesPage.tsx`
- `src/pages/ProfilePage.tsx`

Likely fix: remove unused test imports first, then decide whether hook warnings are legitimate missing dependencies or intentionally stable callbacks.

### 2. Live Order Notification SMS Is Not Consumed

During live checkout/status flows, the SMS worker repeatedly logged:

- `Received unregistered task of type 'sms_worker.send_order_notification_sms'`
- `KeyError: 'sms_worker.send_order_notification_sms'`

Likely cause:

- Core API enqueues task name `sms_worker.send_order_notification_sms` in `services/core-api/src/core_api/services/notification.py`.
- The real task is implemented in `services/sms-worker/src/sms_worker/tasks/notification.py`.
- `services/sms-worker/src/sms_worker/tasks/__init__.py` imports only `send_otp_sms`; it does not import/re-export the notification task.
- `services/sms-worker/src/sms_worker/main.py` uses `celery_app.autodiscover_tasks(["sms_worker.tasks"])`, which is not loading the notification submodule in the running worker.

Likely fix: import/re-export `send_order_notification_sms` in `sms_worker/tasks/__init__.py`, or configure Celery `include=["sms_worker.tasks.otp", "sms_worker.tasks.notification"]`. Add an integration test that starts/imports the worker the same way production does and asserts the task is present in `celery_app.tasks`.

### 3. SMS Log Mode Violates PII/OTP Redaction

The log transport writes raw phone and full SMS body:

- code path: `services/sms-worker/src/sms_worker/clients/log.py`
- tests currently assert raw phone and OTP are present in logs: `services/sms-worker/tests/test_log_transport.py`
- live logs include raw `+799...` phone and OTP code in `[SMS:log]`.

This conflicts with INV-013 in the project instructions: raw phone and OTP code must not be logged. The code comment says this is a dev-only violation, but the root invariant does not grant that exception.

Likely fix: redact phone and code in logs. For local QA, read OTP from Redis directly as the manual scenario already does, or expose a dev-only test helper that is not standard logging.

### 4. Core API Test Suite Is Not Green

Final corrected run with fresh `aura_coffee_test` and `JWT_SECRET_KEY=test-secret`:

- `10 failed, 1084 passed, 1 skipped`

Remaining failures:

- `test_delivery_assignment_state_machine.py::test_list_available_for_courier_returns_only_awaiting`
- `test_main_includes_menu_routers.py::test_main_include_router_call_count`
- `test_menu_admin.py::test_admin_delete_referenced_category_returns_409`
- `test_menu_public.py::test_get_menu_empty_database_returns_empty_list`
- `test_route_cart.py::test_post_cart_item_merges_same_line`
- `test_route_cart.py::test_patch_cart_item_updates_quantity`
- `test_route_cart.py::test_delete_cart_item_removes_line`
- `test_route_cart.py::test_cart_ttl_env_override_respected`
- `test_route_order_history.py::test_single_order_detail_is_not_duplicated`
- `test_schemas_order.py::test_shop_settings_response_round_trip`

Triage:

- Cart merge/patch/delete failures are test-harness drift. `_auth()` creates a fresh UUID every call, so each request uses a different Redis key. Targeted live same-token probe passes.
- Cart TTL test patches `core_api.services.cart.settings`, but that module no longer exposes `settings`.
- Router-count test is stale: expected `13`, actual `18`.
- Order-history test has strict `xfail` text saying route is not registered; the route now exists, so it XPASSes as a failure.
- Shop settings schema test fixture is stale: `auto_close_minutes` is now required.
- Menu public empty DB failure passes individually, so full-suite failure is likely contamination/isolation.
- Admin referenced-category delete works live: `409`, category remains. The unit failure is likely fixture/session-state drift.
- Delivery available-list failure was not reproduced in the live E2E (`courier_available` count was 1), but the isolated unit still returns 2 and needs fixture/query investigation.

Also: tests in `test_route_order_actions.py` require `JWT_SECRET_KEY=test-secret`. Without that explicit env, they fail auth because the container `.env` secret wins over `conftest.py` `setdefault`.

## Quality And Security Notes

- `ruff check .` reports 73 errors, 42 auto-fixable. Categories include unresolved forward-ref names, unused imports/locals, import ordering, and test cleanup.
- Both frontend apps have the same moderate advisory: `postcss <8.5.10`, GHSA-qx2v-qp2m-jg93.
- Admin build passes but warns that the main JS chunk is larger than 500 kB.
- Vitest suites pass but emit warnings:
  - React `act(...)` warnings in customer/admin tests.
  - Admin router basename warnings in `App.test.tsx`.
  - Radix dialog missing description warnings.
  - Missing i18n instance warning in one admin layout test.
- Secret-pattern scan found expected placeholders/dev values in `.env.example` and the isolated generated `.env`; no obvious private keys/AWS/live payment tokens were found. This was a regex scan, not a full secret-scanner guarantee.

## Manual Phase 6 Coverage

I used `docs/phase6_manual_test_scenarios.md` as the guide but executed via API/curl and direct service probes rather than a browser clickthrough. There is no Playwright/Cypress setup in the repo, and I did not add a browser automation dependency during the audit.

Covered successfully:

- preflight health
- staff token acquisition
- customer OTP
- menu read
- cart clear/add
- pickup checkout and full state path
- delivery checkout and courier path
- RBAC probes for protected admin/order routes
- same-token cart merge/patch/delete
- admin referenced-category delete conflict

Not covered as true browser interaction:

- visual UI regression
- actual typed OTP in SPA
- admin/courier/customer clickthrough across every screen
- Yandex Maps positive flow, because the isolated audit env intentionally has no real API key

## Recommended Fix Order

1. Fix customer build/lint unused imports; rerun customer build and lint.
2. Fix SMS worker task registration; add a worker-startup registration test.
3. Redact SMS log transport and update tests/manual docs that currently expect raw phone/OTP in logs.
4. Stabilize Core API test environment: force test JWT secret, reset/partition DB cleanly, and update stale tests.
5. Run and fix `ruff check .`, starting with auto-fixable unused imports/locals.
6. Update `postcss` in both frontend lockfiles.
7. Add a small Playwright E2E suite later for the Phase 6 clickthrough if browser-level confidence is needed.

## Important Logs

- Full summary: `audit-results/audit-summary-rerun.txt`
- Corrected Core API run: `audit-results/core-api-pytest-freshdb-testsecret.log`
- Isolated failing tests: `audit-results/core-api-failing-tests-isolated.txt`
- Live E2E: `audit-results/manual-e2e-flow.log`
- Live E2E log digest: `audit-results/manual-e2e-log-digest.txt`
- Targeted probes: `audit-results/live-targeted-probes.log`
- Customer build/lint: `audit-results/customer-build.log`, `audit-results/customer-eslint.log`
- Admin build/lint: `audit-results/admin-build.log`, `audit-results/admin-eslint.log`
- Ruff: `audit-results/ruff-all.log`
- npm audit: `audit-results/npm-audit-customer.log`, `audit-results/npm-audit-admin.log`
