# Yandex Delivery Decision And Checkout Smoke

This is the operator runbook and evidence log for the Yandex Maps launch gate.
Closed staging already proved the technical server-side proxy path on
2026-05-09. This packet exists to decide whether public launch includes
delivery, prove the delivery checkout path when allowed, and record quota,
billing, and storage/license evidence without committing provider secrets.

Do not run public delivery with unresolved Yandex storage/license questions.
Do not put Yandex API keys, provider screenshots containing secrets, customer
addresses, full coordinates, JWTs, Basic Auth credentials, staging cookies, or
raw provider responses into this file, Git, screenshots, or chat.

## Gate Before Starting

All items must be true before treating delivery as launch-ready:

- [ ] Owner has decided whether public launch is delivery-enabled or
      pickup-only first.
- [ ] Yandex support/account management or owner-approved provider terms confirm
      whether Aura may persist geocoder-derived address text, latitude,
      longitude, precision, and reusable delivery-zone validation data.
- [ ] If a paid/advanced license is required, the owner approved the cost or
      chose pickup-only first.
- [ ] Production key restrictions are configured where supported: server IP
      and/or domain restrictions.
- [ ] Quota, billing threshold, and usage alert owner are recorded.
- [ ] Suggest and Geocoder keys are server-side only.
- [ ] Latest backup and ops health check are green enough to proceed.

If any checkbox is false, do not launch delivery. Use the pickup-first path
below and keep Yandex delivery approval as an owner/provider blocker.

## Decision Record

Record non-secret owner/provider evidence:

```text
decision_time_utc=
launch_mode=<delivery_enabled|pickup_only_first|delivery_deferred>
storage_license_answer=<allowed|paid_required|not_allowed|unknown>
decision_source=<owner|yandex_support|provider_terms|legal_review>
quota_alert_owner=
billing_alert_owner=
usage_dashboard_location_non_secret=
key_restrictions_confirmed=yes/no
notes=
```

Do not paste raw provider terms or private dashboard screenshots here. Link to
approved internal evidence outside Git if needed.

## Pickup-First Path

If the owner chooses pickup-only first or the storage/license answer is not
approved:

1. Record `launch_mode=pickup_only_first` or `delivery_deferred`.
2. Confirm checkout still offers a safe pickup path.
3. Confirm delivery marketing/public text does not promise unavailable delivery.
4. Keep Yandex keys available only for closed-staging testing if needed.
5. Do not use stored Yandex-derived addresses/coordinates for public delivery.

Record:

```text
pickup_checkout_smoke=yes/no
delivery_public_copy_safe=yes/no
delivery_disabled_or_deferred_visible_to_staff=yes/no
followup_owner=
```

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

Record:

```text
preflight_time_utc=
ops_health_failures=
ops_health_warnings=
provider_yandex_split_keys_present=
latest_daily_backup=
```

Expected:

- `failures=0`.
- Yandex split keys are present.
- Any warning is the known manual provider-dashboard alert warning, or it is
  understood before continuing.

## Provider Probe

Probe from inside `core-api` so keys stay server-side:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production \
  exec -T core-api python3 - <<'"'"'PY'"'"'
import os
import httpx

key = os.getenv("YANDEX_MAPS_GEOCODER_API_KEY") or os.getenv("YANDEX_MAPS_API_KEY", "")
print("key_present=", bool(key), "key_len=", len(key), sep="")
r = httpx.get(
    "https://geocode-maps.yandex.ru/1.x/",
    params={"geocode": "Moscow", "apikey": key, "format": "json"},
    timeout=5,
)
print("status=", r.status_code, sep="")
print("body_prefix_len=", len(r.text[:160]), sep="")
PY
'
```

Record only non-secret output:

```text
geocoder_key_present=yes/no
geocoder_http_status=
geocoder_probe_pass=yes/no
```

Expected:

- Key is present.
- Provider returns HTTP 200.
- No key or raw response body is copied into the evidence log.

## App Address And Delivery Checkout Smoke

Use a controlled test customer and a non-sensitive in-zone address agreed for
testing. Do not record the full address or full coordinates.

1. Log in as a customer on closed staging.
2. Open checkout or profile address form.
3. Type the controlled test address.
4. Confirm suggestions appear through Aura API only.
5. Save a typed address without selecting a suggestion.
6. Confirm the address geocodes and stores usable delivery metadata, or fails
   with a user-safe error.
7. Try an intentionally vague address and confirm low precision is rejected.
8. Create a delivery checkout attempt only if launch mode is
   `delivery_enabled`.
9. Confirm delivery zone validation accepts the in-zone address or blocks safely.

Record:

```text
suggestions_through_aura_api=yes/no
direct_yandex_browser_request_seen=yes/no
typed_address_geocode_result=<accepted|safe_error>
vague_address_rejected=yes/no
delivery_checkout_result=<accepted|blocked_safely|not_run_pickup_only>
address_suffix_or_label_only=
full_address_recorded_in_evidence=no
full_coordinates_recorded_in_evidence=no
```

Expected:

- Browser does not call Yandex directly.
- No Yandex key appears in frontend bundles or browser network calls.
- Vague/low-precision input is rejected.
- Delivery either succeeds for the controlled in-zone address or blocks safely.

## Log And Redaction Check

Run after the app smoke:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
COMPOSE="scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production"
logs=$($COMPOSE logs --tail 300 core-api nginx 2>/dev/null || true)
printf "%s\n" "$logs" | grep -Eiq "YANDEX_MAPS_.*(KEY|SECRET)|apikey|api_key|secret|access_token|refresh_token|\\+7[0-9]{10}" \
  && echo "sensitive_pattern=yes" || echo "sensitive_pattern=no"
printf "%s\n" "$logs" | grep -Eiq "maps/(suggest|geocode)\\?text=|geocode=.*(улица|street|проспект|avenue)" \
  && echo "address_query_pattern=yes" || echo "address_query_pattern=no"
'
```

Record:

```text
sensitive_pattern=
address_query_pattern=
redaction_pass=
notes=
```

Expected:

- `sensitive_pattern=no`.
- `address_query_pattern=no`.
- No raw Yandex key, full address, phone, JWT, or secret appears in logs.

## Pass Criteria

The packet passes for delivery launch only if all are true:

- Owner-approved storage/license decision permits the current delivery data
  storage behavior, or the approved paid/provider path is active.
- Quota and billing alert owner are recorded.
- Key restrictions are configured where supported.
- Provider probe returns HTTP 200 from `core-api`.
- Suggest and Geocoder work through Aura API only.
- Low-precision/vague address is rejected.
- Delivery checkout works for a controlled in-zone address or blocks safely.
- Redaction check reports no sensitive or address-query pattern.

The packet passes for pickup-first launch only if all are true:

- Owner chose pickup-only first or delivery remains unapproved.
- Public launch plan does not promise delivery.
- Pickup checkout remains green.
- Delivery follow-up owner is recorded.

## Failure Handling

If the provider probe, app smoke, quota/alert setup, license decision, or
redaction check fails:

1. Do not launch public delivery.
2. Record `launch_mode=pickup_only_first` or `delivery_deferred`.
3. Keep Yandex keys server-side and staging-only until the failure is resolved.
4. Preserve non-secret timestamps, HTTP status codes, and observed user-safe
   errors.
5. If code changes are required, treat the packet as GRACE-sensitive when it
   touches delivery validation, address persistence, PII/logging, checkout
   behavior, or state transitions. Add or update LDD/redaction assertions before
   marking it done.
