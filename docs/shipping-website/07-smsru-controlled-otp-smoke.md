# SMS.ru Controlled OTP Smoke

This is the operator runbook and evidence log for the first real SMS.ru OTP
test on closed staging.

Do not run this packet until the owner answers the SMS.ru questions in
`06-owner-decision-packet.md`. Do not put the real `api_id`, the controlled
phone number, OTP code, JWT, Basic Auth credentials, or staging cookie into this
file, Git, screenshots, or chat.

## Gate Before Starting

All items must be true before switching staging from log mode to real SMS.ru:

- [ ] Owner approved the controlled OTP test window.
- [ ] Controlled phone is available to the operator during the test.
- [ ] SMS.ru account balance is sufficient for at least one OTP test.
- [ ] SMS.ru daily spend or volume limit is active.
- [ ] Owner accepted the shared `SMS.RU` code sender path, or an approved sender
      path exists.
- [ ] Provider alert owner is named for SMS.ru balance/delivery failures.
- [ ] Current closed-staging provider modes are still
      `SMS_BACKEND=log` and `YUKASSA_BACKEND=fake`.
- [ ] Latest backup and ops health check are green enough to proceed.

If any checkbox is false, stop and leave staging in log mode.

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
```

Expected:

- `failures=0`.
- SMS mode is `log`.
- YuKassa mode is `fake`.
- Any warning is the known manual provider-dashboard alert warning, or it is
  understood before continuing.

## Switch To Real SMS.ru

Use the secret-entry flow from
`04-provider-integration-rollout-plan.md#phase-3-enable-smsru-otp`. Enter the
real SMS.ru `api_id` interactively on the VPS; do not paste it into shell
history, docs, or chat.

Minimum target env during the smoke:

```text
SMS_BACKEND=smsru
SMSRU_API_KEY=real_api_id_present_on_server_only
YUKASSA_BACKEND=fake
```

After restart, confirm only non-secret mode values:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/check-ops-health.sh \
  --staging-auth \
  --domain staging.aura-coffee-bakery.ru \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres \
  | grep -E "provider_sms_backend|provider_yukassa_backend|ops_check_finished"
'
```

Record:

```text
switch_time_utc=
provider_sms_backend_after=
provider_yukassa_backend_after=
services_recreated=
```

## Controlled OTP Flow

Use the customer UI on closed staging and the controlled phone only.

1. Request OTP.
2. Wait for the real SMS to arrive.
3. Enter OTP in the UI.
4. Confirm login succeeds.
5. Do not copy the OTP, phone number, JWT, or cookies into the evidence log.

Record:

```text
otp_request_time_utc=
sms_arrival_observed=yes/no
login_success=yes/no
sms_arrival_latency_bucket=<under_30s|30_120s|over_120s|not_received>
ui_error_if_any=
```

## Log And Redaction Check

Run after the controlled login attempt:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
COMPOSE="scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production"
logs=$($COMPOSE logs --tail 250 sms-worker core-api 2>/dev/null || true)
printf "%s\n" "$logs" | grep -q "BLOCK_SMSRU_CALL" \
  && echo "block_smsru_call=yes" || echo "block_smsru_call=no"
printf "%s\n" "$logs" | grep -Eiq "\+7[0-9]{10}|access_token|refresh_token|api_id|secret_key|SMSRU_API_KEY|otp_code|Ваш код|Aura Coffee:" \
  && echo "sensitive_pattern=yes" || echo "sensitive_pattern=no"
'
```

Record:

```text
block_smsru_call=
sensitive_pattern=
redaction_pass=
notes=
```

Expected:

- `block_smsru_call=yes`.
- `sensitive_pattern=no`.
- No raw phone, OTP code, SMS body, JWT, API key, or secret appears in logs.

## Rollback To Log Mode

Rollback immediately after the smoke unless the owner explicitly approves
continuing real SMS mode for the next private test window.

Target rollback env:

```text
SMS_BACKEND=log
SMSRU_API_KEY=
YUKASSA_BACKEND=fake
```

Then recreate the affected services:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/validate-env.sh /opt/aura-coffee/.env.production
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production \
  up -d --force-recreate sms-worker core-api-worker core-api
scripts/production/check-ops-health.sh \
  --staging-auth \
  --domain staging.aura-coffee-bakery.ru \
  /opt/aura-coffee/.env.production \
  /var/backups/aura-coffee/postgres \
  | grep -E "provider_sms_backend|provider_yukassa_backend|ops_check_finished"
'
```

Record:

```text
rollback_time_utc=
provider_sms_backend_final=
provider_yukassa_backend_final=
ops_health_failures_final=
ops_health_warnings_final=
```

## Pass Criteria

The packet passes only if all are true:

- Real SMS arrives on the controlled phone.
- Customer login succeeds.
- `BLOCK_SMSRU_CALL` appears in logs.
- Redaction check reports no sensitive pattern.
- Staging is either intentionally left in `smsru` mode for an approved next
  private test window or rolled back to `SMS_BACKEND=log`.
- `YUKASSA_BACKEND=fake` remains unchanged.

## Failure Handling

If SMS does not arrive, login fails, logs leak sensitive values, or service
health degrades:

1. Roll back to `SMS_BACKEND=log`.
2. Preserve non-secret timestamps, provider event IDs if available, and log
   marker presence.
3. Do not retry with broad phone numbers or higher spend limits until the cause
   is understood.
4. If code changes are required, treat the packet as GRACE-sensitive because it
   touches OTP/SMS/auth/PII/logging. Add or update LDD/redaction assertions
   before marking it done.
