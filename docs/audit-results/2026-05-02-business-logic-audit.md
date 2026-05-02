# Aura Coffee Business Logic and Domain Completeness Audit

Date: 2026-05-02  
Scope: read-only source/test inspection against `docs/PRODUCT_DESIGN_DOCUMENT.md`,
GRACE XML artifacts, and the requested business/domain surfaces.  
Mutation policy: no runtime mutations; no code edits. This report is the only
file created/updated by this audit.

## Executive Summary

Aura Coffee has a strong domain skeleton: enums match PDD state names, RBAC is
centralized and default-deny, cart add rejects stop-listed items, admin settings
and menu media exist, delivery assignment and order transition services use
explicit allow-lists, and seeded QA coverage is broad.

The biggest release blocker is checkout completeness. `services/core-api/src/core_api/services/checkout.py`
still calls local stubs for checkout-time stop-list, working-hours, delivery
minimum, promocode validation, delivery fee, and loyalty accrual estimate. Real
validator modules exist and are unit-tested, but production checkout is not
wired to them. This means several PDD invariants can be bypassed exactly at the
money boundary.

The second blocker is account deletion/anonymization. PDD §6.5 requires
`ACTIVE/BLOCKED -> DELETED` with PII removal, point zeroing, active-order
cancellation/refunds, and tombstone handling. The code has tombstone awareness
in admin views, but no customer/admin delete-account endpoint or service path.

The third blocker is domain drift in notification and payment integration.
There are two notification implementations: a complete `services.notification`
that persists in-app/SMS rows, and a thin `order_notifications` wrapper used by
order lifecycle paths that only sends an unimplemented task name. Payment
webhooks create notification rows directly and do not enqueue the SMS task.

## Compact Matrix

| Area | Status | Evidence | Main Gap | Tests/LDD Required |
| --- | --- | --- | --- | --- |
| INV-001 online prepayment | Partially implemented | Checkout creates `CREATED` + `Payment.PENDING` for non-zero totals; payment worker creates YuKassa intent. | Zero-total orders become `PAID` immediately when points/promo cover all goods; PDD allows no cash but still expects the order lifecycle/payment semantics to be explicit. | Checkout + payment LDD: `orders.create` tx markers; zero-total policy test. |
| INV-002 auth for mutations | Implemented with caveat | `RBACMiddleware` covers all registered routes via `ROUTE_MATRIX`; route coverage test exists. | Current-user dependency decodes JWT only; blocked/deactivated sessions can remain valid, as noted by security audit. | Auth mutation tests; `auth.otp_verify BLOCK_AUTH_VERIFY`; redaction. |
| INV-003 points only on money | Partially implemented | `order_lifecycle._accrue_loyalty` uses `goods_total = order.total - delivery_fee`. | This is after points/promo but uses final order total, not an explicit "money-paid goods subtotal" field; checkout estimate is hard-coded 5%. | Completed-order accrual tests for promo + points + delivery; LDD on transition to `COMPLETED`. |
| INV-004 atomic financials | Partially implemented | Checkout writes order/items/payment/loyalty/promo before commit; payment failure compensation exists. | Checkout validators are stubs; Celery dispatch happens post-commit, so payment-intent creation is not in the same transaction as points/promo reservation. Need outbox/compensation clarity. | Atomic rollback tests; `orders.create BLOCK_TX_*`, payment webhook `BLOCK_TX_PAYMENT`. |
| INV-005 cancellation before cooking | Partially implemented | `cancel_order` allows customer only in `PAID`; admin blocked for `IN_DELIVERY/COMPLETED/CANCELLED`. | Cancel service enqueues refund before DB commit and uses a task side effect inside the transaction boundary; no LDD markers on cancellation chain. | Customer/admin cancel tests with refund failure; `BLOCK_TX_BEGIN/COMMIT`, state marker, redaction. |
| INV-006 stop-list blocks order | Partially implemented | Cart add rejects unavailable item/size/modifier; standalone `validators.stop_list` exists. | Checkout uses a no-op `validate_stop_list`, so items stop-listed after cart add are not rejected at checkout. | Checkout integration test using real validator; `orders.create` no-commit on stop-list. |
| INV-007 working hours | Missing in checkout | Standalone `validators.working_hours.validate_time_slot` exists and is tested. | Checkout calls a no-op `validate_time_slot(requested_time, None)` and never writes `estimated_ready_at`. | Checkout tests for ASAP/open/closed/>24h; tx no-commit on invalid slot. |
| INV-008 delivery radius | Partially implemented | Saved-address creation and checkout delegate to Haversine radius validator. | Inline checkout trusts provided lat/lon and never geocodes free-form address; checkout passes `shop_settings` possibly `None`; Maps outage rejection is not integrated into checkout. | Delivery checkout tests for saved + inline geocode + maps unavailable; redaction. |
| INV-009 delivery minimum | Missing in checkout | Pure `pricing.compute_delivery_fee` and delivery validator exist. | Checkout calls `validate_min_delivery_amount(0, ...)`, a no-op stub, then delivery fee stub returns 0. | Delivery checkout below/equal/above min tests; tx no-commit on below-min. |
| INV-010 role isolation | Implemented with caveat | Matrix restricts admin/user/settings/promos to admin, courier routes to courier, stop-list toggles to admin/barista. | `/api/v1/orders/{id}/status` is route-allowed for courier, but service-level guards reject wrong transitions; acceptable defense-in-depth but route is broad. | Route matrix tests plus transition role tests; LDD for delivery/order transitions. |
| INV-011 one promocode/order | Partially implemented | DTO has one `promocode_code`; conditional increment exists. | Checkout `validate_promocode` returns `None`, so customer promo code is ignored unless tests patch it. Per-user limit is read-only precheck and not atomic in DB. | Real checkout promo tests, concurrent quota/per-user tests; `orders.create` tx markers. |
| INV-012 SMS rate limit | Partially implemented | Minute/hour/day counters exist. | Check and increment are separate Redis operations, allowing concurrent bypass. | Concurrency regression; OTP LDD `BLOCK_OTP_GEN`, `BLOCK_AUTH_VERIFY`, SMS redaction. |
| INV-013 PII isolation/anonymization | Partially implemented | Phone/profile/address separate; profile masks phone; order has address snapshot. | Account deletion/anonymization is missing; orders still FK `users.id` with `RESTRICT`, no tombstone replacement path. | Delete-account tests; redaction; user lifecycle markers required. |
| INV-014 immutable order items | Partially implemented | OrderItem stores snapshots and menu refs are not FK. | No DB trigger/rule prevents UPDATE/DELETE on `order_items`; `orders -> order_items` has `ON DELETE CASCADE`, while PDD forbids physical delete on business tables. | Migration tests for immutability trigger; admin/history tests after menu changes. |
| INV-015 secrets out of code | Partially implemented | Menu media validators reject external/signed-style URLs; workers have safety rails. | Core API settings accept weak placeholders per security audit; not re-audited here. | Settings safety tests; redaction tests. |
| INV-016 explicit transitions | Partially implemented | Shared enums match PDD states; order/delivery services have allow-lists; payment webhook handles known events. | Payment webhook directly sets states without source-state allow-list checks for `PENDING/AWAITING -> SUCCEEDED`; user deletion transition missing; promo state is computed, not persisted enum. | State-machine LDD assertions for order/payment/delivery/user/promo paths. |
| Checkout pricing/loyalty/promo | Partially implemented | DB prices are read for subtotal and order item snapshots. | Delivery fee is always 0; promo validator stub ignores code; accrual estimate hard-coded 5%; checkout does not use `shop_settings.loyalty_percent`. | Full checkout pricing matrix tests and LDD. |
| Stop-list validation | Partially implemented | Cart add and standalone validator are good. | Checkout no-op makes stale carts unsafe. | Real checkout stop-list regression. |
| Working hours/radius/minimums | Partially implemented | Settings model/admin UI/seed exist; standalone validators exist. | Checkout does not wire working hours/minimum/fee and only partially wires radius. | Checkout end-to-end tests. |
| Order/payment/delivery/SMS/user/promo FSMs | Partially implemented | Enums and most services exist. | User deletion absent; payment state source guards weak; SMS notification path split; promo lifecycle computed but checkout unused. | LDD trajectories for all mutable FSMs. |
| Account deletion/anonymization | Missing | Admin code recognizes `DELETED`/tombstone rows. | No delete endpoint/service, no PII wipe, no point zeroing, no active-order cascade. | User lifecycle delete tests, redaction, refund/cancel assertions. |
| Notifications | Partially implemented | Full notification service persists in-app/SMS rows; sms-worker task exists. | Order lifecycle uses thin `order_notifications` task name `sms_worker.order_status_changed`; payment webhook inserts rows directly without SMS enqueue. | Notification integration tests from order/payment transitions to worker task. |
| Shop settings | Implemented with caveat | Singleton model, migration, seed, admin GET/PUT, validation tests. | Runtime checkout does not use settings for fee/min/time/accrual; seed overwrites operator settings when rerun. | Settings-to-checkout integration tests. |
| Menu media | Implemented | Migration 0009, DTO validation, public menu projection, admin validation tests. | No binary upload/storage by design; local media-path contract only. | Existing migration/schema tests sufficient; no LDD. |
| Seeded QA coverage | Implemented with caveat | `phase4_manual_test.py` covers roles, menu, addresses, promos, orders, payments, notifications. | Seed contains dev/test secrets by design and must stay dev-only; report assumes no production seed use. | Seed smoke in isolated test DB only. |
| API endpoint completeness | Partially implemented | Core routers cover menu/cart/orders/history/actions/courier/admin settings/users/promos/maps/profile. | Missing account delete/anonymize endpoint; no customer notification feed endpoint found; payment webhook ingress mismatch covered in security audit. | Route coverage plus OpenAPI/PDD endpoint parity check. |

## Prioritized Remediation

### P0-1: Wire real checkout validators and pricing helpers

Current checkout code still defines and calls no-op or stubbed local functions:

- `validate_stop_list` returns `None`.
- `validate_time_slot` returns `None`.
- `validate_min_delivery_amount` returns `None`.
- `validate_promocode` returns `None`.
- `compute_delivery_fee` returns `0` for delivery.
- `compute_estimated_accrual` uses a hard-coded 5%.

The real modules exist under `services/core-api/src/core_api/services/validators/`
and `services/core-api/src/core_api/services/pricing.py`, but they are not wired
into `create_order`.

Required fix:

1. Run stop-list validation after reading cart and before DB writes, using fresh
   item/size/modifier rows.
2. Load `ShopSettings(id=1)` once and use it for delivery radius, minimum,
   delivery fee, working hours, prep/delivery estimate, and loyalty percent.
3. Compute subtotal before delivery minimum/promocode validation where those
   checks need subtotal.
4. Use `validators.promocode.validate_promocode(code, user_id, subtotal, db)`.
5. Persist `estimated_ready_at` from working-hours validation.
6. Fail before any DB writes when validation fails.

Tests/LDD required:

- Checkout stale stop-list rejection after cart add.
- Delivery below/equal/above minimum and delivery fee/free threshold.
- ASAP inside hours, ASAP next opening, ASAP >24h rejected, requested time outside hours rejected.
- Promo valid/inactive/expired/quota/per-user/min-order and concurrent quota race.
- `grace_logs.assert_trajectory(("orders.create", "BLOCK_TX_BEGIN"), ("orders.create", "BLOCK_STATE_TRANSITION"), ("orders.create", "BLOCK_TX_COMMIT"))` for success.
- Assert no `BLOCK_TX_COMMIT` and no DB rows on validation failures.

### P0-2: Implement account deletion/anonymization

PDD §6.5 requires:

- `ACTIVE -> DELETED` by customer request.
- `BLOCKED -> DELETED` by admin.
- active order cancellation with full refunds.
- PII deletion.
- loyalty balance zeroing.
- irreversible tombstone behavior.

Current code has `UserStatus.DELETED`, `deleted_at`, and admin list/detail
tombstone handling, but no endpoint or service that performs the transition.
Orders, loyalty transactions, notifications, and promocode usages still have
normal FK links to `users.id`; there is no tombstone replacement path.

Required fix:

1. Define the tombstone strategy explicitly: one global anonymous user row or
   per-deleted-user tombstone, then update PDD/XML if needed.
2. Add customer `DELETE /api/v1/profile` and admin delete for blocked users, or
   document a different API shape before implementation.
3. In one controlled transaction or saga: revoke sessions, cancel/refund active
   orders, zero loyalty, remove `user_profiles` and `delivery_addresses`, scrub
   `phone_hash`, set status/deleted_at, and preserve order history against the
   tombstone.
4. Ensure deleted users cannot OTP-login, refresh, order, or appear with PII.

Tests/LDD required:

- Customer delete active account with no active orders.
- Customer delete with `PAID/PREPARING/READY` orders triggers cancellation/refund.
- Admin delete blocked user.
- Deleted/tombstoned user cannot refresh, verify OTP, or mutate state.
- Redaction assertions: no raw phone/name/address/JWT/refresh token.
- User lifecycle and cancellation LDD markers.

### P0-3: Fix notification integration drift

`core_api.services.notification` is the complete domain service: it writes
`notifications` rows and enqueues `sms_worker.send_order_notification_sms`.
But order lifecycle/cancel/delivery code imports `core_api.services.order_notifications`,
which only sends `sms_worker.order_status_changed`. The sms-worker implementation
found in this audit registers `sms_worker.send_order_notification_sms`, not
`sms_worker.order_status_changed`.

Payment webhook paths also create `Notification` rows directly and do not enqueue
the SMS task for `payment.succeeded` or cancellation rows.

Required fix:

1. Pick one notification boundary and delete/deprecate the other.
2. Make order lifecycle, cancellation, delivery, and payment webhook use the
   same service contract.
3. Ensure in-app rows and SMS rows are created consistently, and SMS task names
   match registered sms-worker tasks.
4. Keep notification enqueue after the DB state commit or use an outbox table;
   avoid broker side effects inside uncommitted financial transactions.

Tests/LDD required:

- For each PDD §6.1 notification status: row creation + SMS enqueue where required.
- Payment succeeded and payment failed create expected notification rows and SMS enqueue where required.
- Sms-worker redaction tests for encrypted phone payload and logs.

### P1-1: Add DB-level `order_items` immutability

The ORM and migrations store snapshots correctly, but there is no database guard
against direct `UPDATE` or `DELETE` on `order_items`. Migration 0005 also sets
`orders -> order_items` to `ON DELETE CASCADE`, which conflicts with the PDD's
"physical DELETE on business tables is forbidden" posture.

Required fix:

- Add a Postgres trigger or rule that raises on `UPDATE`/`DELETE` for
  `order_items`.
- Revisit `ON DELETE CASCADE` from orders to order_items; prefer no physical
  order delete path plus restricted FK behavior.
- Add migration tests that direct SQL update/delete fails.

### P1-2: Tighten payment state guards and webhook domain behavior

Payment webhook handlers directly set `payment.status` and `order.status`.
They do not verify the source state is one of the PDD-allowed predecessors before
mutating, beyond idempotent `SUCCEEDED` short-circuit. This weakens INV-016.

Required fix:

- Introduce payment/order transition helpers with explicit source/target checks.
- Ensure `payment.succeeded` cannot move an already cancelled/refunded payment
  or a non-`CREATED` order to paid.
- Ensure `payment.canceled` compensation is idempotent and does not double-return
  points or promo usage.

Tests/LDD required:

- Webhook allowed/disallowed source-state matrix.
- Duplicate success/cancel/refund events.
- `PaymentWorker process_webhook` markers:
  `BLOCK_WEBHOOK_VERIFY`, `BLOCK_TX_PAYMENT`, `BLOCK_STATE_TRANSITION`.

### P1-3: Normalize loyalty accrual and estimates

Pure pricing implements `floor(after_points * loyalty_percent / 100)`, while
checkout estimates `total * 5 // 100`, and completion accrual uses
`(order.total - delivery_fee) * percent // 100`.

Required fix:

- Store enough monetary decomposition on `orders` to compute the exact
  money-paid goods base after promo and points, excluding delivery.
- Use `shop_settings.loyalty_percent` for both checkout estimate and completion.
- Add tests for 100% points, promo+points, delivery fee, free delivery, and zero
  loyalty percent.

### P1-4: Close API endpoint gaps against PDD

Missing or unknown surfaces from source inspection:

- account delete/anonymize endpoint.
- customer notification feed endpoint, despite `notifications(user_id, created_at DESC)`.
- public/payment webhook ingress is covered by the security audit and should be
  remediated with nginx routing plus webhook verification.

Required fix:

- Add an endpoint parity checklist generated from OpenAPI and PDD use cases.
- Treat route coverage as necessary but not sufficient: it proves RBAC mapping,
  not product completeness.

## Verification Notes

Commands run during this audit were source/test inspection only:

- `rg` over PDD, GRACE XML, routers, services, models, migrations, tests, and seeds.
- `sed`/`nl` reads of relevant files.
- `git status --short -- docs/audit-results ...` to avoid overwriting other
  agents' files.

No pytest, app server, Docker, migrations, seed scripts, or runtime API calls
were run because the task explicitly requested non-destructive source/test
inspection and no runtime mutations.

## GRACE/LDD Gate

LDD assertions are required for every remediation that touches:

- checkout transaction boundaries or pricing/loyalty/promo reservation;
- order/payment/delivery/SMS/user/promocode state transitions;
- auth, account deletion, OTP/SMS, PII, payment webhook, refunds, or logging.

Minimum marker coverage to add or run:

- Core API checkout: `[CoreApi][orders.create][BLOCK_TX_BEGIN]`,
  `[CoreApi][orders.create][BLOCK_STATE_TRANSITION]`,
  `[CoreApi][orders.create][BLOCK_TX_COMMIT]`.
- Core API OTP: `[CoreApi][auth.otp_request][BLOCK_OTP_GEN]`,
  `[CoreApi][auth.otp_verify][BLOCK_AUTH_VERIFY]`.
- Core API delivery: `[CoreApi][delivery.assign/accept/pickup/deliver][BLOCK_STATE_TRANSITION]`.
- Payment worker webhook: `[PaymentWorker][process_webhook][BLOCK_WEBHOOK_VERIFY]`,
  `[PaymentWorker][process_webhook][BLOCK_TX_PAYMENT]`,
  `[PaymentWorker][process_webhook][BLOCK_STATE_TRANSITION]`.
- SMS worker: `[SmsWorker][send_otp][BLOCK_SMSRU_CALL]` and notification SMS
  redaction/status assertions.

Current test usage of `grace_logs` is mostly fixture/helper coverage plus one
sms-worker OTP log-backend test. Core API and payment-worker domain paths need
real trajectory assertions before GRACE-sensitive remediations can be marked done.
