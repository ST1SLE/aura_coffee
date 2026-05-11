# Menu And Media Final Approval

This is the operator runbook and evidence log for replacing the closed-staging
draft menu with owner-approved public menu and media content.

Do not run the guarded import until the owner approves the final catalog. Do not
put secrets, signed URLs, private source files, provider keys, customer data,
raw owner spreadsheets with private notes, or unapproved business documents into
Git, screenshots, or chat.

## Gate Before Starting

All items must be true before replacing the closed-staging draft menu:

- [ ] Owner approved all Russian category and item names.
- [ ] Owner approved all English category and item names, or approved launch
      with English names disabled/deferred if the app supports that path.
- [ ] Owner approved prices in kopecks, size labels, volumes, active flags, and
      item availability.
- [ ] Owner approved the current cacao/matcha alternative-milk modifier pricing,
      or a corrected catalog packet is ready.
- [ ] Owner approved all public posters/videos/images for display.
- [ ] Owner approved that media paths are local `/media/menu/{item_code}/...`
      paths, not signed URLs or third-party links.
- [ ] Public legal/offer/refund text will not contradict menu prices,
      availability, pickup, or delivery wording.
- [ ] Latest database backup exists before import.
- [ ] Latest ops health check is green enough to proceed.

If any checkbox is false, do not import. Keep the current closed-staging menu
and record the blocker below.

## Owner Approval Record

Record only non-secret approval evidence:

```text
approval_time_utc=
approver_name_or_role=
catalog_source_version=
ru_names_approved=yes/no
en_names_approved=yes/no
prices_approved=yes/no
size_labels_and_volumes_approved=yes/no
availability_approved=yes/no
alternative_milk_pricing_approved=yes/no
media_quality_approved=yes/no
legal_copy_conflict_checked=yes/no
blockers=
```

Known catalog caveats to resolve explicitly:

- Generic `S/M/L` size labels are currently bridged with volume text in item
  descriptions.
- Cacao/matcha alternative-milk deltas are represented by global milk modifier
  prices.
- English names are operational translations and require owner approval.

## Local Catalog Validation

Run from the repo root:

```bash
scripts/production/validate-menu-catalog.py docs/shipping-website/menu-catalog

scripts/production/validate-menu-catalog.py \
  docs/shipping-website/menu-catalog \
  --media-root web/customer/public/media/menu \
  --require-media-files

scripts/production/validate-menu-media.py web/customer/public/media/menu
```

Record:

```text
catalog_validation_pass=yes/no
media_file_validation_pass=yes/no
media_browser_validation_pass=yes/no
category_count=
item_count=
size_count=
modifier_count=
item_modifier_link_count=
video_count=
poster_count=
validation_notes=
```

Expected:

- CSV headers and references are valid.
- Prices are integer kopecks.
- Media paths stay under `/media/menu/{item_code}/`.
- Every video item has a poster.
- MP4 files pass faststart validation.

Current baseline as of 2026-05-11: structural validation passes for
11 categories, 53 items, 104 size options, 4 modifiers, 28 item-modifier links,
54 videos, and 54 posters. This does not replace owner approval.

## Pre-Import Staging Snapshot

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
preimport_time_utc=
ops_health_failures=
ops_health_warnings=
latest_daily_backup=
provider_sms_backend=
provider_yukassa_backend=
```

Expected:

- `failures=0`.
- Provider modes remain appropriate for closed staging.
- Backup freshness is acceptable.

## Guarded Staging Import

The import is guarded and must be explicit. It archives/hides existing menu
rows before loading the approved packet. It does not delete or mutate orders,
order items, customers, staff, payments, providers, or secrets.

Run only after the gate and validation pass:

```bash
ssh -i ~/.ssh/aura-vps -o IdentitiesOnly=yes deploy@212.8.226.214 '
cd /opt/aura-coffee/app
scripts/production/compose.sh --tls --staging-auth /opt/aura-coffee/.env.production \
  exec -T -e ALLOW_MENU_CATALOG_IMPORT=1 core-api \
  python -m database.seeds.menu_catalog \
    --catalog-dir docs/shipping-website/menu-catalog \
    --replace-existing
'
```

Record sanitized output only:

```text
import_time_utc=
import_exit_status=
categories_imported=
items_imported=
sizes_imported=
modifiers_imported=
item_modifier_links_imported=
```

Expected:

- Command prints `menu_catalog import applied`.
- Counts match the approved catalog packet.
- No secrets, customer data, or private owner data are printed.

## Post-Import Smoke

Run after import:

```bash
scripts/production/check-staging-customer-video-smoke.mjs
scripts/production/check-staging-fake-log-e2e-smoke.mjs
```

Also smoke representative media URLs through the closed-staging origin with
staging access. Record only status codes and content types, not cookies:

```text
poster_sample_status=
poster_sample_content_type=
video_sample_status=
video_sample_content_type=
video_sample_range_status=
```

Record smoke evidence:

```text
menu_visible=yes/no
approved_items_visible=yes/no
archived_or_staging_items_hidden=yes/no
cart_add_smoke=yes/no
fake_log_e2e_pass=yes/no
customer_video_smoke_pass=yes/no
redaction_scan_pass=yes/no
notes=
```

Expected:

- Approved catalog is visible.
- Old draft/staging-only items are not visible to customers.
- Customer can add an approved item to cart.
- Fake/log E2E still reaches completed pickup order.
- Video smoke stays within active request budgets.
- No sensitive log hits.

## Rollback

If the import or smoke fails, stop public launch work and choose the least
destructive rollback:

1. If the issue is media-only, fix or restore media files and rerun media
   validation.
2. If the issue is catalog content and no real customer data depends on it,
   correct the CSV packet and rerun the guarded import.
3. If data state is corrupted or hard to reason about, restore the latest
   database backup only after confirming the owner accepts data loss since that
   backup time.

Record:

```text
rollback_needed=yes/no
rollback_type=<none|media_fix|catalog_reimport|db_restore>
rollback_time_utc=
backup_used_if_any=
post_rollback_ops_health_failures=
post_rollback_menu_visible=yes/no
```

## Pass Criteria

The packet passes only if all are true:

- Owner approval record is complete.
- Catalog validation passes.
- Media filesystem and browser-readiness validation pass.
- Guarded import succeeds with expected counts.
- Approved menu is visible and old draft/staging items are hidden.
- Customer video smoke passes.
- Fake/log E2E smoke passes.
- Redaction scan has no sensitive hits.
- Rollback path is documented and not needed, or was executed successfully.

## Failure Handling

If validation, import, media smoke, cart smoke, or E2E smoke fails:

1. Do not open public traffic.
2. Preserve non-secret validation output, import counts, timestamps, and failed
   item codes.
3. Do not make broad catalog edits without owner approval.
4. If code changes are required, decide whether the GRACE LDD gate applies. It
   is usually not required for static catalog/media validation, but it becomes
   required if the fix touches checkout totals, order snapshots, PII/logging,
   auth, payment, SMS, state transitions, or required markers.
