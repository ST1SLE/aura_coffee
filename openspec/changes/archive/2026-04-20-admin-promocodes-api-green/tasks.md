## 1. Schemas

- [x] 1.1 [core-api] Create `services/core-api/src/core_api/schemas/promocode.py` with: `PromocodeState` (Literal), `PromocodeCreate`, `PromocodeUpdate`, `PromocodeResponse`, `PromocodeListResponse`. `PromocodeCreate.code` has `@field_validator(mode="before")` uppercasing then regex `^[A-Z0-9_-]+$`. Length 1..64 via `StringConstraints`. Discount bounds + date order + per-user≤max via `@model_validator(mode="after")`. `PromocodeUpdate` all-optional, same cross-field checks applied only where both fields present.

## 2. Service

- [x] 2.1 [core-api] Create `services/core-api/src/core_api/services/admin_promocodes.py` with domain exceptions (`PromocodeNotFoundError`, `PromocodeCodeConflictError`, `PromocodeStateConflictError`, `PromocodeActivationPreconditionError`, `FieldLockedAfterUseError`) and `compute_state(promo, now) -> Literal['inactive','active','expired','exhausted']` implementing expired>exhausted>active>inactive priority per PDD §6.6.
- [x] 2.2 [core-api] Add `create_promocode(data: PromocodeCreate, db_session) -> Promocode`: insert with `is_active=False`, `current_uses=0`; on `IntegrityError` rollback + raise `PromocodeCodeConflictError`; single commit.
- [x] 2.3 [core-api] Add `list_promocodes(*, state_filter, code_prefix, page, per_page, db_session, now) -> PromocodeListResponse`: SQL filter by `code ILIKE prefix||'%'`, order `created_at DESC`, load-all, compute state per row, in-Python state filter, slice.
- [x] 2.4 [core-api] Add `get_promocode(promocode_id, db_session) -> Promocode`: `session.get`; raise `PromocodeNotFoundError` on None.
- [x] 2.5 [core-api] Add `update_promocode(promocode_id, patch: PromocodeUpdate, db_session) -> Promocode`: load; if `current_uses>0` and any of {code, discount_type, discount_value} in patch.model_dump(exclude_unset=True) → `FieldLockedAfterUseError(field)`; apply patch; post-merge invariant check (dates, quotas) — rollback+raise `ValueError` on violation; single commit.
- [x] 2.6 [core-api] Add `activate(promocode_id, db_session) -> Promocode`: load; `valid_until is None` → `PromocodeActivationPreconditionError("valid_until required")`; `state=='expired'` → `PromocodeStateConflictError("promocode expired")`; `state=='exhausted'` → `PromocodeStateConflictError("promocode exhausted")`; set `is_active=True`; commit.
- [x] 2.7 [core-api] Add `deactivate(promocode_id, db_session) -> Promocode`: load; `state=='expired'` → `PromocodeStateConflictError("promocode expired")`; set `is_active=False`; commit.

## 3. Router

- [x] 3.1 [core-api] Create `services/core-api/src/core_api/routers/admin_promocodes.py` with `APIRouter(prefix="/api/v1/admin", tags=["admin-promocodes"])` and a `_to_response(promo, now)` helper.
- [x] 3.2 [core-api] `POST /promocodes` → 201; on `PromocodeCodeConflictError` → 409; body = PromocodeCreate (Pydantic handles 422).
- [x] 3.3 [core-api] `GET /promocodes` with query `state`, `code`, `page`, `per_page` (`Query(1,ge=1)`, `Query(20,ge=1,le=100)`); validate `state` against enum/Literal; returns `PromocodeListResponse`.
- [x] 3.4 [core-api] `GET /promocodes/{promocode_id}` → 200 / 404.
- [x] 3.5 [core-api] `PATCH /promocodes/{promocode_id}` → 200 / 404 / 422 (locked field via `HTTPException(422, detail=[{"type":"field_locked_after_use","field":name}])`) / 422 (invariants).
- [x] 3.6 [core-api] `POST /promocodes/{promocode_id}/activate` → 200 / 404 / 422 (no valid_until) / 409 (expired/exhausted).
- [x] 3.7 [core-api] `POST /promocodes/{promocode_id}/deactivate` → 200 / 404 / 409 (expired).

## 4. RBAC + wiring

- [x] 4.1 [core-api] Add six rows to `rbac_matrix.py::ROUTE_MATRIX`: `POST/GET /api/v1/admin/promocodes`, `GET/PATCH /api/v1/admin/promocodes/{promocode_id}`, `POST /api/v1/admin/promocodes/{promocode_id}/activate`, `POST /api/v1/admin/promocodes/{promocode_id}/deactivate`, each `{ADMIN}`.
- [x] 4.2 [core-api] Register router in `services/core-api/src/core_api/main.py`: `from core_api.routers.admin_promocodes import router as admin_promocodes_router` + `app.include_router(admin_promocodes_router)`.

## 5. VERIFY

- [x] 5.1 [core-api] Run `docker compose exec core-api pytest services/core-api/tests/test_admin_promocodes_crud.py services/core-api/tests/test_admin_promocodes_list.py services/core-api/tests/test_admin_promocodes_edit_rules.py services/core-api/tests/test_admin_promocodes_lifecycle.py services/core-api/tests/test_admin_promocodes_rbac.py -v` — all green.
- [x] 5.2 [core-api] Run full suite `docker compose exec core-api pytest services/core-api/tests/ -q` to confirm no pre-existing regression.
