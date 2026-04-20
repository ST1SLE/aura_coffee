## 1. PREREQ — Test infrastructure

- [x] 1.1 [core-api] PREREQ: Extend `services/core-api/tests/_factories/` with `make_promocode(session, **overrides) -> Promocode` (defaults: PERCENT 10, no `valid_until`, `is_active=False`, `current_uses=0`) and `seed_promocodes_across_states(session, now) -> dict[str, list[uuid.UUID]]` (returns four buckets: `inactive`, `active`, `expired`, `exhausted`). Factory file: `tests/_factories/promocodes.py`. No tests yet — reused by admin-promocodes test modules.

## 2. RED — compute_state pure function tests

- [x] 2.1 [core-api] RED: Create `services/core-api/tests/test_admin_promocodes_lifecycle.py::test_compute_state_symbol_absent` — imports `from core_api.services.admin_promocodes import compute_state` inside the test body; asserts the symbol is callable. Expected RED: `ModuleNotFoundError` / `ImportError`.
- [x] 2.2 [core-api] RED: Add `test_compute_state_expired_beats_everything` — constructs a `Promocode` with `valid_until` in the past AND `current_uses >= max_uses` AND `is_active=True`; asserts `compute_state(promo, now) == "expired"`.
- [x] 2.3 [core-api] RED: Add `test_compute_state_exhausted_when_not_expired` — `current_uses >= max_uses`, `valid_until` in the future (or NULL), `is_active=True`; asserts `"exhausted"`.
- [x] 2.4 [core-api] RED: Add `test_compute_state_active_happy` — `is_active=True`, `valid_from <= now`, `valid_until > now`, `current_uses < max_uses`; asserts `"active"`.
- [x] 2.5 [core-api] RED: Add `test_compute_state_inactive_when_is_active_false` — `is_active=False`, otherwise healthy; asserts `"inactive"`.
- [x] 2.6 [core-api] RED: Add `test_compute_state_inactive_before_valid_from` — `is_active=True`, `valid_from > now`; asserts `"inactive"` (not yet active).

## 3. RED — Pydantic schema contract tests

- [x] 3.1 [core-api] RED: Create `services/core-api/tests/test_admin_promocodes_crud.py::test_schemas_module_importable` — imports `PromocodeCreate, PromocodeUpdate, PromocodeResponse, PromocodeListResponse, PromocodeState` from `core_api.schemas.promocode` inside the test body; asserts each is a Pydantic model or a typing alias. Expected RED: `ModuleNotFoundError`.
- [x] 3.2 [core-api] RED: Add `test_promocode_update_all_fields_optional` — instantiates `PromocodeUpdate()` with no args; asserts no exception.
- [x] 3.3 [core-api] RED: Add `test_promocode_state_literal_values` — asserts `get_args(PromocodeState)` equals `("inactive", "active", "expired", "exhausted")` in some order.

## 4. RED — POST /api/v1/admin/promocodes tests (create)

- [x] 4.1 [core-api] RED: Add `test_create_route_registered` to `test_admin_promocodes_crud.py` — inspects `app.routes` for a POST matching exactly `/api/v1/admin/promocodes`; asserts match count is 1 (GREEN target). Expected RED: 0.
- [x] 4.2 [core-api] RED: Add `test_create_happy_path_uppercases_code` — admin POSTs `{"code": "welcome10", "discount_type": "percent", "discount_value": 10, ...}`; asserts status 201, body `code == "WELCOME10"`, `is_active == false`, `current_uses == 0`, body has a `state` field.
- [x] 4.3 [core-api] RED: Add `test_create_duplicate_code_returns_409` — POST with `code="DUP"`, POST again with `code="dup"`; second returns 409.
- [x] 4.4 [core-api] RED: Add `test_create_rejects_bad_pattern` — POST `code="bad code!"`; asserts 422.
- [x] 4.5 [core-api] RED: Add `test_create_percent_over_100_rejected` — `discount_type="percent"`, `discount_value=150`; asserts 422.
- [x] 4.6 [core-api] RED: Add `test_create_fixed_amount_non_positive_rejected` — `discount_type="fixed_amount"`, `discount_value=0`; asserts 422.
- [x] 4.7 [core-api] RED: Add `test_create_dates_inverted_rejected` — `valid_from > valid_until`; asserts 422.
- [x] 4.8 [core-api] RED: Add `test_create_per_user_over_max_uses_rejected` — `max_uses=10`, `max_uses_per_user=20`; asserts 422.
- [x] 4.9 [core-api] RED: Add `test_create_requires_admin_rejects_barista` — same body, `barista_headers`; asserts 403.
- [x] 4.10 [core-api] RED: Add `test_create_requires_token` — no Authorization header; asserts 401.

## 5. RED — GET /api/v1/admin/promocodes tests (list)

- [x] 5.1 [core-api] RED: Create `services/core-api/tests/test_admin_promocodes_list.py::test_list_route_registered` — `app.routes` contains exactly one GET on `/api/v1/admin/promocodes`. Expected RED: 0.
- [x] 5.2 [core-api] RED: Add `test_list_default_state_all_returns_every_bucket` — seeds `seed_promocodes_across_states`; GET with no query; asserts at least one item from each of the four state buckets appears.
- [x] 5.3 [core-api] RED: Add `test_list_state_filter_active` — GET `?state=active`; every returned item has `state == "active"`.
- [x] 5.4 [core-api] RED: Add `test_list_state_filter_expired` — GET `?state=expired`; every returned item has `state == "expired"`.
- [x] 5.5 [core-api] RED: Add `test_list_state_filter_exhausted` — GET `?state=exhausted`; every returned item has `state == "exhausted"`.
- [x] 5.6 [core-api] RED: Add `test_list_state_filter_inactive` — GET `?state=inactive`; every returned item has `state == "inactive"`.
- [x] 5.7 [core-api] RED: Add `test_list_code_prefix_case_insensitive` — seeds `code=WELCOME10`; GET `?code=welc`; asserts the row is present.
- [x] 5.8 [core-api] RED: Add `test_list_per_page_over_100_rejected` — GET `?per_page=101`; asserts 422.
- [x] 5.9 [core-api] RED: Add `test_list_sort_created_at_desc` — seeds two promos at T1 < T2; GET; asserts the T2 row appears before the T1 row.
- [x] 5.10 [core-api] RED: Add `test_list_total_count_after_filter` — seeds 4 active + 2 expired; GET `?state=active`; asserts `total_count == 4`.
- [x] 5.11 [core-api] RED: Add `test_list_pagination_slice` — seeds 25 rows; GET `?page=2&per_page=10`; asserts `len(items) == 10` and `total_count == 25`.
- [x] 5.12 [core-api] RED: Add `test_list_rejects_barista` — `barista_headers`; asserts 403.
- [x] 5.13 [core-api] RED: Add `test_list_requires_token` — no auth; asserts 401.

## 6. RED — GET /api/v1/admin/promocodes/{id} tests (detail)

- [x] 6.1 [core-api] RED: Add `test_detail_route_registered` to `test_admin_promocodes_crud.py` — `app.routes` contains exactly one GET matching `/api/v1/admin/promocodes/{promocode_id}`. Expected RED: 0.
- [x] 6.2 [core-api] RED: Add `test_detail_happy_returns_state_field` — seed a promo; GET the id; assert 200 and `body["state"]` equals `compute_state(promo, now)` (e.g. `"inactive"` for a freshly created promo).
- [x] 6.3 [core-api] RED: Add `test_detail_unknown_id_returns_404` — GET `/api/v1/admin/promocodes/<random-uuid>`; assert 404.
- [x] 6.4 [core-api] RED: Add `test_detail_rejects_customer` — `customer_headers`; asserts 403.

## 7. RED — PATCH /api/v1/admin/promocodes/{id} tests (edit rules)

- [x] 7.1 [core-api] RED: Create `services/core-api/tests/test_admin_promocodes_edit_rules.py::test_patch_route_registered` — `app.routes` contains exactly one PATCH on `/api/v1/admin/promocodes/{promocode_id}`. Expected RED: 0.
- [x] 7.2 [core-api] RED: Add `test_patch_unused_all_fields_editable` — seed promo with `current_uses=0`; PATCH `{"code": "NEW", "discount_value": 25, "valid_until": ...}`; assert 200 and all three fields updated.
- [x] 7.3 [core-api] RED: Add `test_patch_used_rejects_code` — seed promo with `current_uses=1` (direct SQL or factory override); PATCH `{"code": "NEW"}`; assert 422 and error payload contains `type == "field_locked_after_use"` and `field == "code"` (check both FastAPI list-of-dicts shape and flatter shape).
- [x] 7.4 [core-api] RED: Add `test_patch_used_rejects_discount_type` — `current_uses=1`; PATCH `{"discount_type": "fixed_amount"}`; assert 422 with `field == "discount_type"`.
- [x] 7.5 [core-api] RED: Add `test_patch_used_rejects_discount_value` — `current_uses=1`; PATCH `{"discount_value": 99}`; assert 422 with `field == "discount_value"`.
- [x] 7.6 [core-api] RED: Add `test_patch_used_accepts_valid_until` — `current_uses=1`; PATCH `{"valid_until": "<future>"}`; assert 200 and the row's `valid_until` is updated.
- [x] 7.7 [core-api] RED: Add `test_patch_used_accepts_is_active` — `current_uses=1` (non-expired, non-exhausted); PATCH `{"is_active": true}`; assert 200.
- [x] 7.8 [core-api] RED: Add `test_patch_merged_dates_must_be_ordered` — seed `valid_from=T1, valid_until=T3`; PATCH `{"valid_from": "T4"}` where `T4 > T3`; assert 422.
- [x] 7.9 [core-api] RED: Add `test_patch_failed_lock_leaves_row_unchanged` — seed `code="OLD", current_uses=1`; PATCH `{"code": "NEW"}` (rejected with 422); GET the id; assert `code == "OLD"` still.
- [x] 7.10 [core-api] RED: Add `test_patch_rejects_barista` — `barista_headers`; asserts 403.
- [x] 7.11 [core-api] RED: Add `test_patch_unknown_id_returns_404` — random UUID; asserts 404.

## 8. RED — POST /{id}/activate tests

- [x] 8.1 [core-api] RED: Add `test_activate_route_registered` to `test_admin_promocodes_lifecycle.py` — `app.routes` contains exactly one POST on `/api/v1/admin/promocodes/{promocode_id}/activate`. Expected RED: 0.
- [x] 8.2 [core-api] RED: Add `test_activate_requires_valid_until` — seed promo with `valid_until IS NULL`, `is_active=False`; POST activate; assert 422.
- [x] 8.3 [core-api] RED: Add `test_activate_expired_rejected` — seed `valid_until` in the past; assert 409.
- [x] 8.4 [core-api] RED: Add `test_activate_exhausted_rejected` — seed `current_uses=max_uses`, `valid_until` in the future; assert 409.
- [x] 8.5 [core-api] RED: Add `test_activate_happy_sets_is_active_true` — seed eligible inactive promo (valid_until future, current_uses<max_uses); POST activate; assert 200, body `is_active=true`, body `state="active"`, and a fresh DB read confirms `is_active=True`.
- [x] 8.6 [core-api] RED: Add `test_activate_rejects_barista` — `barista_headers`; asserts 403.
- [x] 8.7 [core-api] RED: Add `test_activate_unknown_id_returns_404` — random UUID; asserts 404.

## 9. RED — POST /{id}/deactivate tests

- [x] 9.1 [core-api] RED: Add `test_deactivate_route_registered` to `test_admin_promocodes_lifecycle.py` — `app.routes` contains exactly one POST on `/api/v1/admin/promocodes/{promocode_id}/deactivate`. Expected RED: 0.
- [x] 9.2 [core-api] RED: Add `test_deactivate_expired_rejected` — seed expired (valid_until past), `is_active=True`; POST deactivate; assert 409.
- [x] 9.3 [core-api] RED: Add `test_deactivate_happy_sets_is_active_false` — seed active promo; POST deactivate; assert 200, body `is_active=false`.
- [x] 9.4 [core-api] RED: Add `test_deactivate_unknown_id_returns_404` — random UUID; asserts 404.
- [x] 9.5 [core-api] RED: Add `test_deactivate_rejects_customer` — `customer_headers`; asserts 403.

## 10. RED — RBAC matrix + DELETE absence tests

- [x] 10.1 [core-api] RED: Create `services/core-api/tests/test_admin_promocodes_rbac.py::test_rbac_matrix_rows_admin_only` — asserts all six rows (`POST /`, `GET /`, `GET /{promocode_id}`, `PATCH /{promocode_id}`, `POST /{promocode_id}/activate`, `POST /{promocode_id}/deactivate` under `/api/v1/admin/promocodes`) exist in `ROUTE_MATRIX` with exactly `{ADMIN}`. Expected RED: `KeyError` on first missing row.
- [x] 10.2 [core-api] RED: Add `test_rbac_none_of_six_routes_public` — asserts none of the six `(method, path)` tuples is in `PUBLIC_ROUTES`.
- [x] 10.3 [core-api] RED: Add `test_no_delete_route_registered` — inspects `app.routes`; asserts there is NO route whose method includes DELETE and path matches `/api/v1/admin/promocodes/{...}`.
- [x] 10.4 [core-api] RED: Add `test_validators_promocode_module_unchanged_signature` — introspects `inspect.signature(core_api.services.validators.promocode.validate_promocode)`; asserts parameters `(code, user_id, subtotal, db_session)` — guards against accidental refactor during GREEN.

## 11. VERIFY — RED suite is RED

- [x] 11.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_admin_promocodes_crud.py services/core-api/tests/test_admin_promocodes_list.py services/core-api/tests/test_admin_promocodes_edit_rules.py services/core-api/tests/test_admin_promocodes_lifecycle.py services/core-api/tests/test_admin_promocodes_rbac.py -v` and confirm every NEW test fails (ImportError / ModuleNotFoundError / KeyError / assertion / 404) while every pre-existing test in the suite still passes. Record failing test count in the apply log.
