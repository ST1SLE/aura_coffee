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
- `./scripts/verify-fast.sh` now passes after cleaning up existing ruff drift in shared ORM forward references and two Core API route imports/exception bindings.

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

Start with Wave 0:

1. Review and split the current uncommitted seed/admin/audit changes.
2. Re-run the narrow verification commands for those changes.
3. Commit them in scoped commits.

Then implement Wave 1 as a single GRACE packet with LDD assertions. Do not start Wave 2 customer order pages until backend checkout validation is real enough to trust the order/payment state the UI will display.
