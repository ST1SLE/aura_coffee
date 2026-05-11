# YuKassa Test-Shop Payment Smoke

This is the operator runbook and evidence log for proving the real YuKassa HTTP
path with test-shop credentials on closed staging. It covers payment creation,
webhook ingress, refund/cancel behavior, duplicate webhook handling, invalid
webhook rejection, rollback, and non-secret evidence collection.

Do not run this packet until the owner answers the YuKassa questions in
`06-owner-decision-packet.md`. Do not put test or live shop IDs, secret keys,
webhook secrets, payment tokens, customer phone numbers, JWTs, Basic Auth
credentials, staging cookies, raw webhook bodies, or PAN/card data into this
file, Git, screenshots, or chat.

## Gate Before Starting

All items must be true before switching staging from fake YuKassa mode to the
real YuKassa test HTTP path:

- [ ] Owner/business account has YuKassa test shop access.
- [ ] Test `shopId` and test secret key are available to the operator through a
      private channel.
- [ ] Test webhook URL is configured or ready to configure:
      `https://staging.aura-coffee-bakery.ru/api/webhooks/yukassa`.
- [ ] Test shop is subscribed to `payment.succeeded`, `payment.canceled`,
      `refund.succeeded`, and `refund.canceled`.
- [ ] Source verification method is known: YuKassa source IP allowlist and/or
      configured signature secret.
- [ ] Owner/accountant has at least a test-mode 54-FZ/receipt decision, or the
      test explicitly records that fiscal behavior is not approved for live
      launch yet.
- [ ] Staff test operator is available for order visibility and refund/cancel
      actions.
- [ ] Current closed-staging payment mode is still `YUKASSA_BACKEND=fake`.
- [ ] Latest backup and ops health check are green enough to proceed.

If any checkbox is false, stop and leave staging in fake payment mode.

## Preflight Snapshot

Run from the operator machine:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/check-ops-health.sh \
  --staging-auth \
  --domain staging.aura-coffee-bakery.ru \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres
'
```

Record non-secret evidence:

```text
preflight_time_utc=
ops_health_failures=
ops_health_warnings=
latest_daily_backup=
provider_sms_backend_before=
provider_yukassa_backend_before=
webhook_url_configured_in_provider=yes/no
source_verification_method=<ip_allowlist|signature|both|unknown>
```

Expected:

- `failures=0`.
- YuKassa mode is `fake`.
- SMS mode is known and acceptable for the closed-staging test window.
- Any warning is the known manual provider-dashboard alert warning, or it is
  understood before continuing.

## Switch To YuKassa Test Shop

Enter YuKassa test credentials interactively on the VPS. Do not paste secrets
into shell history, docs, or chat.

Minimum target env during the smoke:

```text
YUKASSA_BACKEND=live
YUKASSA_BASE_URL=https://api.yookassa.ru/v3
YUKASSA_SHOP_ID=test_shop_id_present_on_server_only
YUKASSA_SECRET_KEY=test_secret_key_present_on_server_only
YUKASSA_WEBHOOK_IPS=trusted_provider_ips_or_current_approved_value
YUKASSA_WEBHOOK_SIGNATURE_SECRET=only_if_configured
```

After editing `/opt/aura-coffee/.env.production`, recreate the affected
services:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/validate-env.sh /opt/aura-coffee/.env.production
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production \
  up -d --force-recreate payment-worker payment-webhook core-api
scripts/production/check-ops-health.sh \
  --staging-auth \
  --domain staging.aura-coffee-bakery.ru \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres \
  | grep -E "provider_yukassa_backend|ops_check_finished"
'
```

Record:

```text
switch_time_utc=
provider_yukassa_backend_after=
payment_services_recreated=
```

## Payment And Webhook Flow

Use closed staging and a controlled pickup order.

1. Log in as a customer.
2. Create a small pickup order.
3. Follow the YuKassa confirmation URL.
4. Pay with a YuKassa test card from official test-shop tooling.
5. Return to Aura Coffee.
6. Confirm the order moves from `CREATED` to `PAID`.
7. Confirm the payment object in YuKassa test dashboard is marked test-mode.
8. Confirm staff can see the paid order.

Record:

```text
payment_request_time_utc=
customer_redirected_to_yukassa=yes/no
returned_to_aura=yes/no
order_paid_in_aura=yes/no
provider_payment_test_mode=yes/no
staff_order_visible=yes/no
provider_event_id_or_payment_id_suffix_only=
```

Do not record the full payment ID if the provider dashboard treats it as
sensitive. A short suffix is enough for correlating private notes.

## Webhook Marker And Redaction Check

Run after the payment attempt:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
COMPOSE="scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production"
logs=$($COMPOSE logs --tail 300 payment-webhook payment-worker core-api 2>/dev/null || true)
printf "%s\n" "$logs" | grep -q "BLOCK_WEBHOOK_VERIFY" \
  && echo "block_webhook_verify=yes" || echo "block_webhook_verify=no"
printf "%s\n" "$logs" | grep -q "BLOCK_TX_PAYMENT" \
  && echo "block_tx_payment=yes" || echo "block_tx_payment=no"
printf "%s\n" "$logs" | grep -Eiq "secret_key|YUKASSA_SECRET_KEY|authorization:|Bearer |access_token|refresh_token|card|pan|password|api_id|raw webhook|phone|\\+7[0-9]{10}" \
  && echo "sensitive_pattern=yes" || echo "sensitive_pattern=no"
'
```

Record:

```text
block_webhook_verify=
block_tx_payment=
sensitive_pattern=
redaction_pass=
notes=
```

Expected:

- `block_webhook_verify=yes`.
- `block_tx_payment=yes`.
- `sensitive_pattern=no`.
- No raw webhook body, secret key, PAN, JWT, phone, or PII appears in logs.

## Refund, Duplicate, And Rejection Drills

Run these in test mode before any live credentials are used.

1. Create and pay a second controlled test order.
2. Trigger the admin cancel/refund path.
3. Confirm refund/payment state in Aura.
4. Confirm refund state in the YuKassa test dashboard.
5. Replay or resend a duplicate webhook if provider tooling supports it.
6. Send or request an invalid source/signature test if feasible.
7. Confirm duplicate terminal events do not double-apply side effects.
8. Confirm invalid webhooks are rejected before mutation.

Record:

```text
refund_order_created=yes/no
refund_state_in_aura=
refund_state_in_yukassa=
duplicate_webhook_tested=yes/no/not_supported
duplicate_idempotent=yes/no/not_supported
invalid_webhook_tested=yes/no/not_supported
invalid_webhook_rejected=yes/no/not_supported
payment_side_effects_double_applied=yes/no
```

## Rollback To Fake Mode

Rollback immediately after the smoke unless the owner explicitly approves
continuing YuKassa test mode for the next private test window.

Target rollback env:

```text
YUKASSA_BACKEND=fake
YUKASSA_SHOP_ID=dev-shop
YUKASSA_SECRET_KEY=dev-secret
```

Disable the test-shop webhook in the YuKassa dashboard if the provider account
will not be used again immediately. Then recreate the affected services:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/validate-env.sh /opt/aura-coffee/.env.production
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production \
  up -d --force-recreate payment-worker payment-webhook core-api
scripts/production/check-ops-health.sh \
  --staging-auth \
  --domain staging.aura-coffee-bakery.ru \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres \
  | grep -E "provider_yukassa_backend|ops_check_finished"
'
```

Record:

```text
rollback_time_utc=
provider_yukassa_backend_final=
webhook_disabled_in_dashboard=yes/no/not_needed
ops_health_failures_final=
ops_health_warnings_final=
```

## Pass Criteria

The packet passes only if all are true:

- Test-shop payment redirects through YuKassa and returns to Aura.
- Aura order moves to `PAID`.
- Webhook verification and payment transaction markers are visible.
- Redaction check reports no sensitive pattern.
- Refund/cancel behavior is proven or explicitly recorded as not supported by
  current provider tooling.
- Duplicate terminal events are idempotent or explicitly recorded as not
  testable with available tooling.
- Invalid webhook source/signature is rejected or explicitly recorded as not
  testable with available tooling.
- Staging is either intentionally left in YuKassa test mode for an approved next
  private test window or rolled back to `YUKASSA_BACKEND=fake`.

## Failure Handling

If payment, webhook, refund, duplicate, invalid-source, redaction, or service
health checks fail:

1. Disable the test webhook if it is causing repeated callbacks.
2. Roll back to `YUKASSA_BACKEND=fake`.
3. Preserve non-secret timestamps, provider event IDs or short suffixes, marker
   presence, and observed states.
4. Do not switch to live credentials until the test-shop failure is understood.
5. If code changes are required, treat the packet as GRACE-sensitive because it
   touches payments, webhooks, refunds, transaction boundaries, state
   transitions, secrets, and PII/logging. Add or update LDD/redaction assertions
   before marking it done.
