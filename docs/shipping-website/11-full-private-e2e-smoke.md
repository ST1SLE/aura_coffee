# Full Private End-To-End Smoke

This is the operator runbook and evidence log for the final private launch
rehearsal before live cutover. It proves the customer, staff, provider, menu,
media, backup, and redaction paths together while staging is still closed.

Do not run this packet against public traffic. Do not paste real secrets, full
phone numbers, OTP codes, JWTs, payment card data, raw webhook bodies, staging
credentials, cookies, private owner notes, or full customer addresses into Git,
screenshots, chat, or evidence logs.

## Preconditions

All items must be true before the full private smoke starts:

- [ ] Closed staging is reachable over HTTPS and protected by staging auth.
- [ ] Latest ops health check exits with `failures=0`, or every warning is
      explicitly accepted for this rehearsal.
- [ ] Latest daily backup exists and the previous restore drill result is still
      acceptable.
- [ ] SMS.ru controlled OTP packet passed:
      `07-smsru-controlled-otp-smoke.md`.
- [ ] YuKassa test-shop payment/refund/rejection packet passed:
      `08-yukassa-test-payment-smoke.md`.
- [ ] Yandex delivery decision and smoke packet passed, or launch is explicitly
      approved as pickup-only:
      `09-yandex-delivery-decision-smoke.md`.
- [ ] Final menu/media approval and guarded import packet passed:
      `10-menu-media-final-approval.md`.
- [ ] Staff test operator accounts exist for admin, barista, and courier roles,
      or the run is scoped to pickup-only staff surfaces.
- [ ] Legal/privacy/offer/refund/consent owner has approved private rehearsal
      scope and confirms public launch remains blocked until final legal copy is
      published.

If any provider remains intentionally mocked, stop here and run only the
waiting-room checks in the last section.

## Evidence Header

Record non-secret context:

```text
run_time_utc=
operator=
domain=
release_tag_or_commit=
database_schema=
provider_sms_backend=
provider_yukassa_backend=
yandex_delivery_mode=<delivery_enabled|pickup_only>
menu_catalog_version=
latest_daily_backup=
ops_health_failures=
ops_health_warnings=
```

Expected provider modes for the full private rehearsal:

```text
SMS_BACKEND=smsru
YUKASSA_BACKEND=live
YUKASSA_BASE_URL=https://api.yookassa.ru/v3
```

For this packet, `YUKASSA_BACKEND=live` means the real YuKassa HTTP client with
test-shop credentials, not live money. Do not use live shop credentials until
the controlled live cutover packet.

## Pre-Smoke Server Checks

Run from the VPS or through SSH:

```bash
cd /opt/aura-coffee/app

scripts/production/check-ops-health.sh \
  --staging-auth \
  --domain staging.aura-coffee-bakery.ru \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres

scripts/production/compose.sh --tls --staging-auth \
  /opt/aura-coffee/.env.production ps
```

Record:

```text
ops_health_pass=yes/no
compose_services_running=yes/no
health_endpoint_ok=yes/no
tls_days_remaining=
backup_fresh=yes/no
disk_usage_ok=yes/no
provider_dashboard_alert_warning_accepted=yes/no
```

Expected:

- Required services are running.
- Public `/health` succeeds through the closed-staging origin.
- TLS, backup age, and disk checks are acceptable.
- Provider dashboard alert warnings are accepted only if a named owner exists.

## Customer And Media Smoke

Run the automated customer video smoke from the operator machine:

```bash
scripts/production/check-staging-customer-video-smoke.mjs
```

Then manually verify the owner-approved public menu:

1. Open `https://staging.aura-coffee-bakery.ru/` on desktop width.
2. Open the same site on mobile width.
3. Browse categories and item details.
4. Add one approved pickup item to cart.
5. Confirm old draft/staging-only items are hidden.
6. Check representative poster and video behavior on a slow connection profile
   if the browser supports it.

Record:

```text
customer_video_smoke_pass=yes/no
desktop_menu_visible=yes/no
mobile_menu_visible=yes/no
approved_items_visible=yes/no
draft_items_hidden=yes/no
cart_add_pass=yes/no
representative_media_status_ok=yes/no
slow_network_media_acceptable=yes/no/not_run
notes=
```

Expected:

- Video smoke keeps requests within the bounded playback budget.
- Posters stay visible while video loads.
- Approved menu and media are visible.
- Cart accepts an approved item.

## Real SMS.ru OTP Login

Use only the controlled test phone from the SMS.ru packet.

1. Request OTP from the customer UI.
2. Confirm the SMS arrives on the controlled phone.
3. Verify OTP.
4. Confirm the customer session is created.
5. Inspect recent `sms-worker` and `core-api` logs.

Record:

```text
otp_sms_received=yes/no
otp_login_pass=yes/no
smsru_marker_present=yes/no
auth_verify_marker_present=yes/no
sms_redaction_pass=yes/no
```

Expected:

- Logs include the required SMS/auth markers.
- Logs do not include raw phone, OTP code, SMS body, JWT, password, or API key.

## Pickup Order And YuKassa Test Payment

Use YuKassa test-shop credentials with the real HTTP client.

1. Create a small pickup order from the customer cart.
2. Follow the YuKassa confirmation URL.
3. Pay using a YuKassa test card.
4. Return to Aura Coffee.
5. Confirm the order changes from `CREATED` to `PAID`.
6. Confirm the payment is marked as test-mode in the YuKassa dashboard.
7. Inspect `payment-webhook` and `payment-worker` logs.

Record:

```text
pickup_order_created=yes/no
yukassa_redirect_pass=yes/no
test_payment_paid=yes/no
order_paid_in_aura=yes/no
webhook_verify_marker_present=yes/no
tx_payment_marker_present=yes/no
payment_redaction_pass=yes/no
```

Expected:

- Payment redirect works.
- Webhook reaches `/api/webhooks/yukassa`.
- Order reaches `PAID`.
- Logs include webhook verification before payment mutation markers.
- Logs do not include raw webhook body, secret key, PAN, JWT, or PII.

## Staff Operations Smoke

Run against the paid pickup test order:

1. Staff logs in at `/admin/`.
2. Admin or barista opens order feed and detail.
3. Barista moves order through the approved pickup status path.
4. Confirm customer order detail reflects status changes.
5. Confirm courier-only surfaces are not available to barista/admin accounts
   outside their role.

Record:

```text
admin_login_pass=yes/no
barista_login_pass=yes/no
order_feed_visible=yes/no
order_detail_visible=yes/no
pickup_status_flow_pass=yes/no
customer_status_updates_visible=yes/no
role_surfaces_correct=yes/no
staff_redaction_pass=yes/no
```

Expected:

- Staff can operate the controlled paid pickup order.
- Role visibility matches the assigned staff roles.
- No raw credentials, JWTs, phone numbers, or full addresses appear in logs.

## Delivery Smoke Or Pickup-Only Decision

Run this section only if delivery is approved for launch. If launch is
pickup-only, record the pickup-only owner decision and skip delivery actions.

Delivery flow:

1. Create a customer delivery address inside the allowed zone.
2. Confirm Suggest works through Aura API, not direct browser calls to Yandex.
3. Save a typed address without selecting a suggestion and confirm server-side
   geocoding succeeds or blocks safely.
4. Create a small delivery order with YuKassa test payment.
5. Confirm staff/courier surfaces show the delivery assignment path.
6. Try a vague or out-of-zone address and confirm checkout blocks safely.

Record:

```text
pickup_only_decision=yes/no
yandex_license_storage_approved=yes/no/not_applicable
suggest_proxy_pass=yes/no/not_run
typed_address_geocode_pass=yes/no/not_run
delivery_order_created=yes/no/not_run
delivery_payment_paid=yes/no/not_run
courier_surface_pass=yes/no/not_run
out_of_zone_blocked=yes/no/not_run
yandex_key_exposure_check_pass=yes/no/not_run
```

Expected:

- Yandex keys stay server-side.
- Delivery checkout works only for approved, safely geocoded addresses.
- Pickup remains available if delivery is deferred.

## Refund And Failure Drill

Use a second controlled YuKassa test order or the approved refund test order
from the YuKassa packet.

1. Trigger admin cancel/refund path.
2. Confirm refund/payment state in Aura.
3. Confirm refund state in YuKassa test dashboard.
4. Replay duplicate webhook if test tooling allows.
5. Send an invalid webhook source/signature test if feasible.

Record:

```text
refund_order_created=yes/no
refund_triggered=yes/no
refund_state_in_aura=
refund_state_in_yukassa=
duplicate_webhook_idempotent=yes/no/not_run
invalid_webhook_rejected=yes/no/not_run
refund_redaction_pass=yes/no
```

Expected:

- Refund/cancel behavior is known before live cutover.
- Duplicate terminal events do not double-apply side effects.
- Invalid webhook attempts are rejected before mutation.
- Logs remain redacted.

## Final Redaction And Marker Review

Inspect recent logs for marker presence and sensitive-data absence. Record only
the result, not complete logs.

```bash
cd /opt/aura-coffee/app

scripts/production/compose.sh --tls --staging-auth \
  /opt/aura-coffee/.env.production \
  logs --since 60m core-api payment-webhook payment-worker sms-worker nginx
```

Record:

```text
auth_markers_present=yes/no
sms_markers_present=yes/no
payment_markers_present=yes/no
state_transition_markers_present=yes/no
raw_phone_absent=yes/no
otp_absent=yes/no
jwt_absent=yes/no
api_keys_absent=yes/no
raw_webhook_body_absent=yes/no
pan_absent=yes/no
full_address_absent=yes/no
```

Expected:

- Required markers for OTP, payment webhook, and payment transaction paths are
  present.
- No redaction-sensitive values appear in recent logs.

## Pass Criteria

The packet passes only if all are true:

- Ops health is acceptable.
- Customer menu/media smoke passes.
- Real SMS.ru OTP login passes.
- YuKassa test payment reaches `PAID`.
- Staff can operate the controlled pickup order.
- Delivery passes or pickup-only launch is explicitly approved.
- Refund/failure drill passes or every unrun edge case has an owner-approved
  reason.
- Logs contain required markers and no sensitive values.
- Evidence is sanitized and complete enough to support the cutover decision.

## Waiting-Room Checks If Providers Remain Blocked

If SMS.ru, YuKassa, Yandex, legal, or final menu approval is still blocked,
do not run the full private smoke. Keep staging healthy with the existing
non-money checks:

```bash
scripts/production/check-staging-customer-video-smoke.mjs
scripts/production/check-staging-fake-log-e2e-smoke.mjs
```

These waiting-room checks do not replace the full private smoke. They only keep
the closed-staging baseline warm until provider and owner gates open.

## Failure Handling

If any section fails:

1. Do not proceed to controlled live cutover.
2. Preserve non-secret timestamps, order IDs if safe, provider test event IDs,
   marker presence, and sanitized failure symptoms.
3. Roll back only the failing provider/config path when possible.
4. If code changes are required, decide whether the GRACE LDD gate applies. It
   usually applies for fixes touching auth, SMS, payments, webhooks, refunds,
   transaction boundaries, PII/logging, state transitions, or required markers.
