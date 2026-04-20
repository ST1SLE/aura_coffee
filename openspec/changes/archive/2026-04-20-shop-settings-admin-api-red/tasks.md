## 1. Prereqs (no TDD)

- [x] 1.1 [core-api] PREREQ: Inspect existing fixtures in `services/core-api/tests/conftest.py`
  for admin/barista/courier/customer clients and `migrated_db_session`; confirm they
  are reusable. No code changes in this task — report gaps only.
- [x] 1.2 [core-api] PREREQ: Grep `ShopSettingsResponse` usage in
  `services/core-api/src/core_api/routers/` so RED tests can confirm the
  additive field `auto_close_minutes` will not break a customer-facing endpoint.

## 2. RED: migration 0008 contract

- [x] 2.1 [core-api] RED: Create
  `services/core-api/tests/test_migration_0008_auto_close.py` with
  `test_upgrade_adds_auto_close_minutes_column` — asserts after upgrade head
  that `shop_settings.auto_close_minutes` exists, is INTEGER, NOT NULL,
  server default "60". Must fail (migration file does not exist yet).
- [x] 2.2 [core-api] RED: Add `test_downgrade_drops_auto_close_minutes_column`
  to the same file — downgrades to revision 0007 and asserts column absent.
  Must fail (migration file missing).
- [x] 2.3 [core-api] RED: Add `test_seed_row_has_auto_close_default` to the
  same file — runs the seed on migrated DB and asserts the singleton row
  carries `auto_close_minutes = 60`. Must fail.

## 3. RED: GET /api/v1/admin/settings

- [x] 3.1 [core-api] RED: Create
  `services/core-api/tests/test_admin_shop_settings_get.py` with
  `test_admin_get_returns_default_snapshot` — uses the admin client + seeded DB,
  expects 200 and JSON containing all current fields plus
  `auto_close_minutes = 60`. Must fail (router not registered).

## 4. RED: PUT /api/v1/admin/settings

- [x] 4.1 [core-api] RED: Create
  `services/core-api/tests/test_admin_shop_settings_put.py` with
  `test_admin_put_updates_all_fields` — admin sends a complete body,
  expects 200, response matches input, `updated_at` advanced. Must fail.
- [x] 4.2 [core-api] RED: Add `test_singleton_check_rejects_second_row` to
  the same file — attempts a direct ORM insert of id=2 using `ShopSettings`
  model, asserts `IntegrityError` from `ck_shop_settings_singleton`. Must
  fail until migration + model are updated (or pass if constraint already
  holds; see D5 — test wording must still depend on the new column so it
  imports an attribute that does not exist yet, guaranteeing RED).

## 5. RED: validation

- [x] 5.1 [core-api] RED: Create
  `services/core-api/tests/test_admin_shop_settings_validation.py` with a
  `pytest.mark.parametrize` table covering: `shop_lat=91`, `shop_lon=181`,
  `loyalty_percent=101`, `free_delivery_threshold < min_delivery_amount`,
  `auto_close_minutes=0`, `auto_close_minutes=1441`, `working_hours` missing
  `sun` key, `working_hours.mon.open='25:00'`,
  `working_hours.mon={open:'10:00',close:'10:00'}` — each expects 422.
  Must fail (endpoint + schema not implemented).
- [x] 5.2 [core-api] RED: Add `test_working_hours_day_off_accepted` — sends
  body where `working_hours.tue = null` with other fields valid, expects 200.
  Must fail.

## 6. RED: RBAC

- [x] 6.1 [core-api] RED: Create
  `services/core-api/tests/test_admin_shop_settings_rbac.py` with
  `test_get_forbidden_for_barista`, `test_get_forbidden_for_courier`,
  `test_get_forbidden_for_customer`, `test_get_unauthorized_without_token` —
  all four expect 403/401. Must fail (route not in RBAC matrix yet).
- [x] 6.2 [core-api] RED: Add analogous PUT cases:
  `test_put_forbidden_for_barista`, `test_put_forbidden_for_courier`,
  `test_put_forbidden_for_customer`, `test_put_unauthorized_without_token`.
  Must fail.

## 7. Verify RED state

- [x] 7.1 [core-api] VERIFY: Run
  `pytest services/core-api/tests/test_migration_0008_auto_close.py
  services/core-api/tests/test_admin_shop_settings_*.py` and confirm every new
  test is RED (failure or ImportError). Record the summary in the commit body.
