# Aura Coffee Audit Synthesis and Remediation Plan

Date: 2026-05-02

Source reports:

- `docs/audit-results/2026-05-02-customer-ux-audit.md`
- `docs/audit-results/2026-05-02-staff-ux-audit.md`
- `docs/audit-results/2026-05-02-business-logic-audit.md`
- `docs/audit-results/2026-05-02-security-audit.md`
- `docs/audit-results/2026-05-02-verification-audit.md`

This synthesis continues the interrupted audit session `019de45e-0dcc-7322-93a1-4f5592520489`.
It is intentionally a planning artifact only: no runtime code is changed here.

## Current Repository State

Already committed:

- `a0de29d Adapt customer UI from Drinkit research`

Pending uncommitted implementation work in the main tree:

- `database/seeds/phase4_manual_test.py` - richer idempotent manual QA seed.
- `docs/phase6_manual_test_scenarios.md` - manual guide updates for the richer seed and current QA flow.
- `web/customer/public/media/menu/cappuccino-qa/{hero.mp4,poster.webp}` - local QA media referenced by the seed.
- `web/admin/src/components/Layout.tsx` and related tests/i18n - admin/barista logout UI.
- `web/admin/tsconfig.tsbuildinfo` - build artifact changed by admin verification; review whether to keep or revert before commit.

New documentation/audit artifacts:

- April 30 broad-audit artifacts and mission plan remain under `docs/audit-results/` and `docs/AUDIT_REMEDIATION_MISSION_PLAN.md`.
- May 2 focused audit reports are listed above.

Before starting remediation, commit or deliberately split the pending seed/admin/audit work so later fixes do not mix with QA-data and logout changes.

## Executive Summary

The system has a strong base: centralized RBAC, explicit state enums, working menu/cart/profile surfaces, richer QA data, payment-worker tests, SMS LDD/redaction coverage, and a real admin/barista shell. The blockers are not cosmetic. They cluster around checkout correctness, post-checkout customer experience, courier operations, notification drift, security hardening, and release verification discipline.

The highest-risk gaps are:

1. Production checkout still uses local stub validators for stop-list, working hours, delivery minimum, delivery fee, promocodes, and loyalty estimate.
2. Customer checkout navigates to `/orders/:id`, but the SPA has no order detail route and `/orders` is still a placeholder.
3. Courier frontend and backend disagree on assignment response shape, and assignments become visible before orders are `READY`.
4. Notification integration has split service boundaries and mismatched task names across order lifecycle, payment webhook, and SMS worker.
5. GRACE/LDD markers are emitted in important code paths, but most required trajectories are not asserted in tests.
6. Security hardening is needed before production: account/session revocation, atomic OTP rate limiting, webhook ingress/trust, secret safety rails, and safer browser token storage.

## Release-Blocking Remediation Waves

### Wave 0 - Land Current QA/Admin Work

Purpose: preserve already completed local work in coherent commits before starting sensitive remediation.

Recommended split:

1. Manual QA seed and docs:
   - `database/seeds/phase4_manual_test.py`
   - `docs/phase6_manual_test_scenarios.md`
   - `web/customer/public/media/menu/cappuccino-qa/*`
   - relevant audit log if intentionally committed
2. Admin logout UI:
   - `web/admin/src/components/Layout.tsx`
   - `web/admin/src/components/Layout.test.tsx`
   - `web/admin/src/i18n/locales/en/common.json`
   - `web/admin/src/i18n/locales/ru/common.json`

Decision needed:

- Do not include `web/admin/tsconfig.tsbuildinfo` unless the project intentionally tracks this generated state. Prefer confirming current repo practice before staging it.

Verification before commit:

```bash
docker compose exec -T core-api python database/seeds/phase4_manual_test.py
docker compose exec -T core-api pytest services/core-api/tests/test_route_coverage.py services/core-api/tests/test_rbac_matrix.py -q
cd web/admin && npm test -- Layout.test.tsx --run
cd web/admin && npm run lint && npm run build
```

GRACE/LDD:

- Seed/doc/admin-frontend logout UI does not itself require LDD if no backend auth behavior changes.
- The seed touches sensitive domain data only as deterministic local QA setup; keep it clearly dev/test scoped.

### Wave 1 - Checkout Correctness at the Money Boundary

Primary source: business-logic audit P0-1.

Scope:

- Wire real checkout validators and pricing helpers into `services/core-api/src/core_api/services/checkout.py`.
- Use `ShopSettings` for working hours, delivery fee/min/free threshold, prep/delivery estimates, and loyalty percent.
- Use real stop-list and promocode validators.
- Ensure validation fails before order/payment/loyalty/promo rows are written.

Why first:

- This touches INV-004 financial atomicity and multiple PDD checkout invariants.
- Customer UX can look correct while checkout still accepts invalid orders, so backend correctness must lead.

Required tests:

- stale stop-list after cart add;
- delivery below/equal/above minimum;
- paid/free delivery threshold;
- ASAP/open/closed/specific requested-time cases;
- valid/inactive/expired/quota/per-user/min-order promo cases;
- validation failures leave no order/payment rows;
- loyalty estimate uses settings percent.

Required LDD:

- `orders.create -> BLOCK_TX_BEGIN -> BLOCK_STATE_TRANSITION -> BLOCK_TX_COMMIT` on success.
- No `BLOCK_TX_COMMIT` and no persisted rows on validation failure.
- Redaction assertions for address and auth-sensitive log paths touched by checkout.

Status:

- Current worktree already wires `services/core-api/src/core_api/services/checkout.py` to real stop-list, working-hours, delivery minimum/radius/fee, promocode, finite-inventory, loyalty, and `ShopSettings` pricing paths. Focused verification passed for checkout, saved-address delivery checkout, pure validators, and atomic promocode increment tests; required `orders.create` LDD success/no-commit failure assertions are covered by `services/core-api/tests/test_checkout_service.py`.

### Wave 2 - Customer Order Detail, Payment Handoff, and History

Primary source: customer UX audit P0s.

Scope:

- Add customer order-detail client and `/orders/:orderId` page.
- Replace placeholder `/orders` with real history.
- After checkout, route to the detail/status page.
- Poll for `confirmation_url` while order is `CREATED`, redirect to payment when present, and refresh status at the PDD freshness interval.
- Render immutable item snapshots, totals, state timeline, zero-total order behavior, and customer cancel while allowed.

Why after Wave 1:

- The UI should display and poll a trustworthy order/payment model. It should not compensate for backend checkout gaps in React.

Required tests:

- checkout redirects to a defined route;
- order detail handles `CREATED`, `PAID`, `PREPARING`, `READY`, `IN_DELIVERY`, `COMPLETED`, `CANCELLED`;
- `confirmation_url` redirect path;
- zero-total order path;
- customer cancel visible only in allowed state;
- history empty/active/completed states;
- loyalty/history links no longer dead-end.

Required LDD:

- Backend customer cancel and payment/status paths require order/payment marker assertions.
- Pure frontend route rendering does not require LDD, but must not change price ownership or calculate business totals client-side.

Status:

- Current worktree already implements the Wave 2 customer order surface: `web/customer/src/App.tsx` routes `/orders` and `/orders/:orderId`; `web/customer/src/api/orders.ts` provides create/detail/history/cancel/repeat clients; `OrdersPage` renders real customer history with immutable item snapshots and repeat-order handoff; `OrderDetailPage` handles all PDD §6.1 customer-visible statuses, confirmation URL handoff, local fake YuKassa polling, zero-total paid orders, customer cancel when `PAID`, and repeat-order navigation.
- Backend endpoints are present and verified for own-order detail, own-order history, customer cancel, and repeat-order cart rebuild: `services/core-api/src/core_api/routers/orders.py`, `order_history.py`, and `order_actions.py`.
- Focused frontend verification passed: `npm --prefix web/customer test -- OrdersPage.test.tsx OrderDetailPage.test.tsx CheckoutPage.test.tsx api/orders.test.ts --run` (`36` tests) and `npm --prefix web/customer run typecheck`.
- Focused backend verification passed: `docker compose exec -T core-api pytest services/core-api/tests/test_route_order_history.py services/core-api/tests/test_route_orders.py services/core-api/tests/test_route_order_actions.py services/core-api/tests/test_order_repeat_service.py -q` (`60` tests).
- LDD gate: this packet made no runtime state-machine, payment, transaction, auth, PII, or logging code changes. Existing backend cancel/order lifecycle LDD coverage remains the gate for those flows; this Wave 2 update is audit status documentation only.

### Wave 3 - Courier Operations Contract and Ready Handoff

Primary source: staff UX audit P0s plus security courier PII finding.

Scope:

- Normalize courier assignment response schema across available, mine, take, pickup, and deliver.
- Align available/take semantics with PDD: courier should not take a delivery before the order is ready unless the PDD is explicitly changed.
- Decide whether admins can supervise courier routes; either add backend admin-supervision endpoints or make `/courier` courier-only.
- Minimize address data in the available feed; expose full delivery details only to the assigned courier.

Required tests:

- frontend renders actual backend response shapes;
- preparing delivery order is not available/takeable;
- ready delivery order becomes available;
- mine endpoint includes enough assigned-order detail;
- available feed omits full address/apartment/comment;
- admin route behavior matches backend RBAC decision.

Required LDD:

- Delivery assignment transition trajectories for assign/take/pickup/deliver.
- No mismatched delivery/order state beliefs.
- Redaction assertions for address payload/log paths.

Status:

- Current backend already normalizes the courier assignment contract across available, mine, take, pickup, and deliver responses in `services/core-api/src/core_api/routers/courier.py`; RBAC keeps the courier API courier-only, and `web/admin/src/App.tsx` now mounts `/courier` behind a courier-only `ProtectedRoute`.
- Current delivery-assignment service already filters available assignments to `AWAITING_COURIER` rows whose parent order is `READY`, blocks `take` for non-READY orders with `order_not_ready`, and redacts `delivery_address` on the available feed while keeping full delivery details on assigned rows.
- Added frontend defense-in-depth for INV-013: `AvailableTab` now passes `showAddress={false}` so available courier cards hide delivery addresses even if an upstream payload accidentally includes one; `MineTab` still renders assigned-order address details.
- Focused frontend verification passed: `npm --prefix web/admin test -- CourierPage.test.tsx AvailableTab.test.tsx MineTab.test.tsx api/courier.test.ts --run` (`19` tests) and `npm --prefix web/admin run typecheck`.
- Focused backend verification passed: `docker compose exec -T core-api pytest services/core-api/tests/test_delivery_assignment_state_machine.py services/core-api/tests/test_courier_endpoints.py -q` (`52` tests).
- LDD/redaction gate: asserted `delivery.accept`, `delivery.pickup`, and `delivery.deliver` `BLOCK_STATE_TRANSITION` trajectories with no mismatched beliefs; asserted available-feed redaction by checking no full address/comment appears in the service row, plus frontend coverage that available cards do not render address text before assignment.

### Wave 4 - Notification Boundary Cleanup

Primary source: business-logic audit P0-3.

Scope:

- Choose one notification service boundary.
- Make order lifecycle, cancellation, delivery, and payment webhook use the same service contract.
- Align Celery task names with registered sms-worker tasks.
- Decide whether notification enqueue happens post-commit or via outbox; avoid broker side effects inside uncommitted financial transactions.

Required tests:

- expected in-app notification rows for order/payment/delivery events;
- SMS enqueue for required status changes;
- payment success/failure notification paths;
- no unregistered task names;
- sms-worker log redaction for notification SMS.

Required LDD:

- LDD assertions for any touched order/payment/delivery transitions.
- SMS redaction checks for phone, OTP/code-like content, JWT/API key, and message body.

Status:

- The canonical notification boundary is `core_api.services.notification` plus shared pure text helpers in `packages/shared/src/shared/notifications.py`; the legacy `core_api.services.order_notifications` import path now delegates to that boundary, and payment webhook code uses the same shared matrix and registered `sms_worker.send_order_notification_sms` task name.
- Added post-commit SMS enqueue semantics for Wave 4: core-api notification SMS dispatch and payment-worker webhook SMS dispatch now register SQLAlchemy `after_commit` callbacks and clear pending callbacks on rollback, so broker side effects cannot publish for rolled-back notification rows.
- Focused core-api verification passed: `docker compose exec -T core-api pytest services/core-api/tests/test_notification_service.py services/core-api/tests/test_order_lifecycle.py services/core-api/tests/test_order_cancel.py services/core-api/tests/test_delivery_assignment_state_machine.py -q` (`138` tests).
- Focused payment-worker verification passed: `docker compose exec -T payment-worker pytest services/payment-worker/tests/test_webhook.py -q` (`22` tests).
- Focused sms-worker verification passed: `docker compose exec -T sms-worker pytest services/sms-worker/tests/test_notification_task.py services/sms-worker/tests/test_otp_task_log_backend.py -q` (`13` tests).
- LDD/redaction gate: core order lifecycle/cancel/delivery tests asserted their touched transition markers with no mismatched beliefs; payment webhook tests asserted `process_webhook` `BLOCK_TX_PAYMENT` and `BLOCK_STATE_TRANSITION` trajectories; SMS-worker tests assert notification and OTP logs do not expose raw phone, OTP/code-like message bodies, JWT-shaped values, API keys, or plaintext SMS bodies.

## Production-Hardening Waves

### Wave 5 - Auth, Session, and OTP Security

Primary sources: security audit P1-1, P1-2, P1-5, P2-1, P2-4.

Scope:

- Re-check customer/staff status during refresh and protected mutations, or introduce revocable session/version claims.
- Revoke sessions on customer block/delete and staff deactivate.
- Make OTP rate-limit check+increment atomic.
- Stop returning deterministic `phone_hash` to public clients.
- Add staff login rate limiting.
- Move long-lived browser refresh tokens out of localStorage; plan cookie/CSRF model before code.

Required LDD:

- `auth.otp_request BLOCK_OTP_GEN`
- `auth.otp_verify BLOCK_AUTH_VERIFY`
- redaction for phone, OTP, JWT, password, refresh token.

Status:

- Backend Wave 5 controls are present and verified in the current worktree: customer refresh uses DB-backed status checks and indexed session revocation, protected Bearer access rejects blocked/deleted customers and inactive/role-mismatched staff, staff refresh re-reads `staff_accounts`, OTP send-code uses atomic `reserve_rate_limit`, send-code no longer returns public `phone_hash`, and staff login has Redis-backed failed-login throttling.
- Focused backend verification passed: `docker compose exec -T core-api pytest services/core-api/tests/test_auth_endpoints.py services/core-api/tests/test_staff_auth.py services/core-api/tests/test_admin_users_block.py -q` (`43` tests) plus `ruff check` for the auth/router/service/test files.
- LDD/redaction gate: auth tests assert `auth.otp_request` `BLOCK_OTP_GEN`, `auth.otp_verify` `BLOCK_AUTH_VERIFY`, and `staff.auth_login` `BLOCK_AUTH_VERIFY`; captured logs are checked for no raw phone, OTP code, JWT, password, refresh token, or deterministic `phone_hash`.
- Browser token-storage migration is now implemented as the dedicated follow-up packet: customer and staff refresh tokens are set as path-scoped HttpOnly `SameSite=Strict` cookies, refresh/logout read the cookie first with JSON body fallback for non-browser clients, and both frontends stopped persisting refresh tokens in localStorage. SameSite=Strict is the CSRF boundary for the same-origin nginx deployment; bearer access tokens still protect logout.
- Focused cookie-migration verification passed: `docker compose exec -T core-api pytest services/core-api/tests/test_auth_endpoints.py services/core-api/tests/test_staff_auth.py -q` (`34` tests), `npm --prefix web/customer test -- AuthProvider.test.tsx api/auth.test.ts api/client.test.ts --run` (`25` tests), `npm --prefix web/admin test -- api/client.test.ts LoginPage.test.tsx --run` (`32` tests), customer/admin `typecheck`, customer/admin `lint`, and `ruff check` for the touched Core API auth files/tests.
- Cookie-migration LDD/redaction gate: successful OTP verify still asserts `auth.otp_request -> auth.otp_verify` with no raw phone, phone hash, OTP, or refresh token in captured logs; staff login throttling still asserts `staff.auth_login BLOCK_AUTH_VERIFY` with no password/JWT/refresh token leakage; new cookie tests assert HttpOnly/SameSite/Path attributes, cookie-backed refresh rotation, and cookie clearing on failed refresh/logout.

### Wave 6 - Payment Webhook Ingress and Secret Safety

Primary sources: security audit P1-3, P1-4 and business-logic payment state guard findings.

Scope:

- Route `/api/webhooks/yukassa` through nginx to payment-webhook.
- Overwrite, not append, trusted proxy IP headers for webhook traffic.
- Add signature verification if configured.
- Fail fast on weak Core API JWT/encryption secrets outside dev.
- Tighten payment source-state guards before mutating payment/order states.

Required LDD:

- `process_webhook BLOCK_WEBHOOK_VERIFY`
- `process_webhook BLOCK_TX_PAYMENT`
- `process_webhook BLOCK_STATE_TRANSITION`
- redaction for raw webhook body and payment secrets.

Status:

- Wave 6 controls are present and verified in the current worktree: nginx has an exact `/api/webhooks/yukassa` route to `payment-webhook` before the generic `/api/` route, the webhook route overwrites `X-Forwarded-For` with `$remote_addr`, and compose keeps nginx dependent on `payment-webhook`.
- Payment webhook hardening is present in `services/payment-worker/src/payment_worker/webhook.py`: optional HMAC-SHA256 signature verification rejects invalid or missing signatures before JSON parsing and before dispatch, event idempotency remains commit-bound, and guarded payment/refund handlers reject forbidden source states or duplicate terminal events without mutating rows or emitting a state-transition marker.
- Core API secret safety rails are present in `services/core-api/src/core_api/settings.py`: outside explicit `AURA_ENV=dev`, placeholder/short JWT secrets and malformed/all-zero PII encryption keys fail fast without echoing raw secret values in validation errors.
- Focused verification passed: `/usr/bin/python3 -m pytest tests/test_nginx_webhook_route.py -q` (`4` tests), `docker compose exec -T payment-worker pytest services/payment-worker/tests/test_webhook.py services/payment-worker/tests/test_settings.py services/payment-worker/tests/test_settings_safety_rail.py -q` (`35` tests), and `docker compose exec -T core-api pytest services/core-api/tests/test_settings_safety_rail.py -q` (`13` tests).
- Focused lint passed for the touched payment-worker webhook/settings/tests, Core API settings/tests, and nginx route regression test.
- LDD/redaction gate: payment webhook tests assert `process_webhook` `BLOCK_WEBHOOK_VERIFY`, `BLOCK_TX_PAYMENT`, and `BLOCK_STATE_TRANSITION` on successful transitions; guarded duplicate/forbidden-source tests assert no state-transition marker and no mismatched beliefs; signature tests assert raw webhook body and signature secret are absent from captured logs. Core settings tests assert rejected secret values are not echoed in validation errors.

### Wave 7 - Account Deletion and PII Anonymization

Primary sources: business-logic audit P0-2 and customer UX deletion gap.

Scope:

- Define tombstone strategy before implementation.
- Add customer/admin deletion endpoints according to PDD.
- Revoke sessions, cancel/refund active orders, zero loyalty, scrub phone/profile/address PII, preserve order history.

Required LDD:

- User lifecycle deletion markers.
- Cancellation/refund markers when active orders exist.
- Redaction assertions for phone, name, address, JWT, refresh token.

Status:

- Backend packet landed in this worktree: customer `DELETE /api/v1/profile`, admin `DELETE /api/v1/admin/users/{user_id}` for blocked users, in-place tombstone strategy, session revocation, loyalty zeroing, profile/address PII removal, cancellable active-order cancellation, and LDD/redaction tests.
- `IN_DELIVERY` orders intentionally block deletion until terminal state because PDD §6.1 forbids `IN_DELIVERY -> CANCELLED`; PDD §6.5 now documents that deletion note.

## Verification and Release Gate Work

Primary source: verification audit.

Recommended sequence:

1. Add `scripts/verify-fast.sh` and `scripts/verify-full.sh`.
2. Add missing frontend `typecheck` scripts or update `docs/verification-plan.xml` after choosing the canonical command.
3. Add LDD assertion tests for checkout, OTP verify, delivery assignment, order transitions, cancellation, and payment webhook.
4. Add a small Playwright smoke suite for customer checkout, barista transitions, courier delivery, and admin logout -> barista login role switching.
5. Add readiness checks for core-api, payment-webhook, nginx, and workers.
6. Add Python dependency/security audit gate and update vulnerable `cryptography`.
7. Add non-destructive QA reset script; keep `docker compose down -v` documented as destructive.

Status:

- Items 1-2 are already present in the repository: `scripts/verify-fast.sh`, `scripts/verify-full.sh`, and frontend `typecheck` scripts are tracked.
- Item 3 started with the cancellation slice: `services/core-api/tests/test_order_cancel.py` now asserts `orders.cancel` transaction/state/commit markers, no commit marker on failed validation, and redaction of free-text cancellation reason content.
- Item 3 continued with the order lifecycle slice: `services/core-api/tests/test_order_lifecycle.py` now asserts `order_lifecycle.transition_order` transaction/state/commit markers and no state/commit marker on forbidden transition validation.
- `./scripts/verify-fast.sh` now passes after cleaning up existing ruff drift in shared ORM forward references and two Core API route imports/exception bindings.
- Item 5 is covered by `scripts/check-readiness.sh`, now wired into `scripts/verify-full.sh`: it checks direct Core API health, direct payment-webhook health, nginx canonical `/health`, and Celery worker pings.
- Item 6 is covered by `cryptography>=46.0.7,<47.0` in core-api and sms-worker, a regenerated core-api lock pinned to `cryptography 46.0.7`, and mandatory `scripts/check-python-deps.sh` execution from `scripts/verify-full.sh`; host-side `pip-audit` now reports no known vulnerabilities for core-api, payment-worker, sms-worker, and shared.
- Item 7 is covered by guarded `scripts/reset-qa-data.sh` plus `database/seeds/reset_qa_data.py`: it refuses outside dev/test/local unless `ALLOW_QA_RESET=1`, deletes rows owned by known Phase 4 QA seed identifiers/users, re-runs the manual seed, and keeps `docker compose down -v` documented as a destructive full-stack wipe rather than routine QA reset.
- Final release-gate run passed on 2026-05-02 with `AURA_E2E_SKIP_BROWSER_INSTALL=1 ./scripts/verify-full.sh` after Chromium had already been installed by the browser-smoke run. The canonical command remains `./scripts/verify-full.sh`; the gate covered readiness, Alembic drift detection and upgrade, Python ruff, shared/Core API/payment-worker/sms-worker tests, customer/admin lint/typecheck/Vitest/npm audit, Playwright browser smoke, and `pip-audit` for core-api, payment-worker, sms-worker, and shared.
- Full-gate regressions found and fixed during the release-gate run:
  - Alembic metadata drift: shared ORM metadata now declares the indexes and unique constraints already applied by migrations, so `alembic check` reports `No new upgrade operations detected`.
  - Stale Core API test assumptions: admin-user list service tests now isolate their rows by display-name prefix under a non-empty Postgres test DB, and the router registration count test reflects the current 19 routers.
  - Environment-only issue: the Core API image was rebuilt because `respx` was already declared in the dev extra but the running container predated that dependency; nginx was restarted after Core API recreation so it re-resolved the upstream container IP.
  - Final release-readiness rerun fixed two stale test assumptions: `order_items.order_id` now expects `ON DELETE RESTRICT`, and the pickup autoclose no-op test no longer depends on an empty shared Postgres test database.

## Remaining May 2 P1/P2 Review

Current status after the implemented waves and final green full gate:

1. No release-significant P1/P2 blockers remain from the May 2 remediation set. Remaining work is polish/backlog unless the release definition expands.

Additional release-readiness items completed in follow-up packets:

1. Customer checkout input completeness is now implemented: `web/customer/src/pages/CheckoutPage.tsx` sends `promocode_code`, `points_to_use`, and `requested_time`, and renders server-owned checkout estimates/free-delivery guidance from `POST /api/v1/orders/estimate`.
2. DB-level `order_items` immutability is now enforced by migration `0011_order_items_immutability.py`: the `orders -> order_items` FK is `ON DELETE RESTRICT`, and Postgres triggers reject direct `UPDATE` and `DELETE` on `order_items`.
3. Tracked CI now exists at `.github/workflows/verify.yml`: on `push` to `main`/`dev` and on pull requests it installs `uv`, generates a dev `.env`, builds/starts the Compose stack, runs `./scripts/verify-full.sh`, uploads Docker logs on failure, and shuts the stack down. `scripts/setup-worktree-env.sh` now offsets `PAYMENT_WEBHOOK_PORT` too, so the workflow and local parallel worktrees do not share that host binding.
4. Browser smoke now exists under `tests/e2e`: `scripts/verify-browser-smoke.sh` installs Playwright, runs the QA-scoped reset, and verifies customer pickup checkout, admin logout to barista role switching, barista pickup transitions, and courier take/pickup/deliver through the browser. `./scripts/verify-full.sh` now includes this gate.

Items that look downgraded to polish/backlog, not immediate release blockers:

- Staff mobile navigation and order-feed freshness are now addressed in code: admin/barista layout has a role-filtered mobile bottom nav, and the staff orders feed polls active orders every 5 seconds.
- SMS.ru redaction, Python dependency auditing, courier available-feed PII minimization, payment webhook ingress/guards, auth/session hardening, account deletion, notification boundary cleanup, and non-destructive QA reset are covered by the completed wave statuses above.
- Remaining customer visual polish and stale/flaky-test curation should be separate backlog packets unless the release definition expands to include them. Staff table/card mobile optimization, the failed-refund admin exception queue, and the customer notification feed have been handled in follow-up backlog packets.

## Parallelization Guidance

Safe to parallelize after Wave 0:

- Wave 2 frontend order pages can run in parallel with Wave 5 auth hardening only if no backend order/action endpoints are being changed in the same branch.
- Verification script/CI scaffolding can run in parallel with pure frontend UI work if it does not rewrite package manifests touched elsewhere.
- Design polish for auth/profile/addresses can run after functional order/status routes land.

Keep sequential:

- Wave 1 checkout correctness.
- Wave 3 courier state semantics.
- Wave 4 notification boundary cleanup.
- Payment webhook and secret validation.
- Account deletion/anonymization.
- Any PDD §6 state-machine change.

Reason: these touch shared invariants, transaction boundaries, RBAC, PII, and LDD marker expectations. Overlapping branches here would make verification weaker, not faster.

## Next Recommended Action

Before starting the next design-change session:

1. Keep the unrelated untracked `docs/agent-context/` and design-reference files out of remediation commits unless they are deliberately promoted into the release artifact set.
2. Treat new design work as a separate packet from the completed May 2 release-readiness remediation.
