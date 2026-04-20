## Context

The RED change archived at `openspec/changes/archive/2026-04-20-admin-promocodes-api-red` authored 63 failing tests (52 assertion failures + 11 tests that pass today because the RBAC middleware returns 403 for unregistered admin paths). GREEN's job is to add the minimum code that turns every new assertion green without regressing pre-existing suites.

The contract from RED:
- `compute_state(promo, now) -> Literal['inactive','active','expired','exhausted']` is the single source of truth for state derivation. Priority: expired > exhausted > active > inactive.
- Six endpoints under `/api/v1/admin/promocodes`, ADMIN-only (INV-010), no DELETE.
- `code` is canonicalized by server-side UPPER before pattern validation and persistence.
- PATCH distinguishes unused (all fields editable) from used (`current_uses > 0`, locked fields `code/discount_type/discount_value` → 422 with `type="field_locked_after_use"` and `field=<name>`).
- Activate requires `valid_until NOT NULL`, rejects expired (409) and exhausted (409).
- Deactivate rejects expired (409). Expired is terminal per PDD §6.6.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Turn the RED suite green with zero test edits.
- Keep the service layer free of FastAPI dependencies — pure Python + SQLAlchemy. Routers do the HTTP translation.
- Keep each write-op to one `session.commit()` (INV-004).
- Reuse existing middleware for 401/403 — the RBAC matrix does the heavy lifting; router stays thin.
- Small, predictable files: service ~200 lines, schema ~120 lines, router ~180 lines.

**Non-Goals:**
- Adding new tests, widening coverage, or editing existing tests.
- Performance tuning beyond the default Python-side state filter.
- Introducing a repository/unit-of-work pattern — the existing style in `services/order_history.py` is direct SQLAlchemy with an explicit `db_session` parameter; we match it.
- Implementing `GET /api/v1/admin/promocodes/{id}/usages` or any usage-statistics surface.
- Loyalty, checkout, pricing — separate zones.

## Decisions

### D1 — Service layer raises domain exceptions; router translates to HTTP

**Decision:** `services/admin_promocodes.py` SHALL raise three domain exceptions:
- `PromocodeNotFoundError` → 404.
- `PromocodeCodeConflictError` → 409 (duplicate code on create).
- `PromocodeStateConflictError(reason: str)` → 409 (activate/deactivate guards: `"promocode expired"`, `"promocode exhausted"`).
- `FieldLockedAfterUseError(field: str)` → 422 with body `{"detail": [{"type": "field_locked_after_use", "field": "<name>"}]}`.
- `PromocodeActivationPreconditionError(reason: str)` → 422 (activate without `valid_until`).

Router has a thin try/except block per endpoint that maps these to `HTTPException`. Pydantic validation errors propagate naturally (422). `IntegrityError` from `create_promocode` (on duplicate `code`) is caught inside the service and translated to `PromocodeCodeConflictError`.

**Why:** Keeps the service testable in isolation (no FastAPI import). Keeps the HTTP status code decision centralized in the router. Matches the pattern of `validate_promocode` which raises `PromocodeValidationError`.

### D2 — `code` canonicalization lives in the Pydantic `field_validator`

**Decision:** `PromocodeCreate.code` SHALL have a `@field_validator("code", mode="before")` that uppercases the input. The regex `^[A-Z0-9_-]+$` is applied AFTER uppercasing so lowercase letters pass canonicalization but punctuation fails. Length 1..64 is enforced via `Annotated[str, StringConstraints(min_length=1, max_length=64)]`.
**Why:** Single place for the transform. The router doesn't need to know about it. `PromocodeUpdate.code` uses the same validator (still blocked by field-lock on used promos, but canonical when allowed on unused promos).

### D3 — Cross-field invariants in `@model_validator(mode="after")`

**Decision:** For `PromocodeCreate`:
- If both `valid_from` and `valid_until` are set: `valid_from < valid_until`.
- If both `max_uses` and `max_uses_per_user` are set: `max_uses_per_user <= max_uses`.
- If `discount_type == "percent"`: `0 < discount_value <= 100`.
- If `discount_type == "fixed_amount"`: `discount_value > 0`.

For `PromocodeUpdate`: same checks, but only applied when BOTH relevant fields are present in the patch (for cross-field checks). The router separately merges patch with the loaded row and re-validates the merged state — see D6.
**Why:** Pydantic-level validation produces 422 automatically. No router-side branching needed.

### D4 — `compute_state` is the single source of truth

**Decision:** One pure function with signature `compute_state(promo: Promocode, now: datetime) -> Literal[...]`. Used by:
- `get_promocode` (populating response).
- `list_promocodes` (filter + populate response).
- `activate` (expired/exhausted guards).
- `deactivate` (expired guard).
- `_to_response` helper.

Priority as pinned by RED D2: expired > exhausted > active > inactive.

### D5 — List-side state filter done in Python after SQL load

**Decision:** `list_promocodes` SHALL:
1. Build a SQL query filtered by `code ILIKE :prefix || '%'` if `code` is provided.
2. Order by `created_at DESC`.
3. Load all rows matching the SQL filter (no pagination yet).
4. Compute state for each row.
5. If `state_filter != "all"`, drop rows with a different state.
6. `total_count = len(filtered_rows)`.
7. Slice `[((page-1)*per_page):(page*per_page)]`.
8. Build `PromocodeListResponse`.

**Why:** The promocode count for MVP is bounded (dozens, not millions). SQL-side state derivation would duplicate the Python logic and risk drift. This decision is anchored in RED D10.

### D6 — PATCH flow: load → compute old state → field-lock check → merge → invariant check → save

**Decision:** `update_promocode(promocode_id, patch: PromocodeUpdate, db_session)`:
1. `SELECT ... FOR UPDATE`-equivalent (regular load is sufficient; writes are rare and admin-only — no need for SELECT FOR UPDATE).
2. If `promo.current_uses > 0`:
   - For each of `code`, `discount_type`, `discount_value` set in `patch.model_dump(exclude_unset=True)`, raise `FieldLockedAfterUseError(field_name)`.
3. Apply patch fields to the ORM instance.
4. Re-check cross-field invariants on the **merged** row: `valid_from < valid_until` if both not None; `max_uses_per_user <= max_uses` if both not None. Violations raise `ValueError` → router returns 422.
5. `session.commit()`.
6. Return `promo`.

**Why:** Failing fast on field-lock before mutating the instance preserves INV-004 (no partial state). Post-merge invariant check handles the case where the patch changes only `valid_from` but the old `valid_until` is now earlier.

### D7 — Activate / deactivate: load → compute → guard → set → commit

**Decision:**
```
activate(promocode_id, db_session):
    promo = _get_or_raise(promocode_id, db_session)
    if promo.valid_until is None:
        raise PromocodeActivationPreconditionError("valid_until required")
    state = compute_state(promo, now=_utcnow())
    if state == "expired":
        raise PromocodeStateConflictError("promocode expired")
    if state == "exhausted":
        raise PromocodeStateConflictError("promocode exhausted")
    promo.is_active = True
    db_session.commit()
    return promo

deactivate(promocode_id, db_session):
    promo = _get_or_raise(promocode_id, db_session)
    state = compute_state(promo, now=_utcnow())
    if state == "expired":
        raise PromocodeStateConflictError("promocode expired")
    promo.is_active = False
    db_session.commit()
    return promo
```
**Why:** Pins the logic from RED §8 and §9 directly. No ambiguity.

### D8 — 422 payload shape for `field_locked_after_use`

**Decision:** The router endpoint catches `FieldLockedAfterUseError` and returns:
```json
{
  "detail": [
    {"type": "field_locked_after_use", "field": "<name>"}
  ]
}
```
Via `HTTPException(status_code=422, detail=[{"type": "field_locked_after_use", "field": name}])`.

RED tests (`test_admin_promocodes_edit_rules._extract_field_from_detail`) handle both list-of-dicts and flat-dict shapes, so the list form is safe and matches FastAPI's built-in error style.
**Why:** Consistent with FastAPI's native validation errors. Easy for the admin UI to parse.

### D9 — Timezone handling: `datetime.now(UTC)` in the service

**Decision:** `compute_state` accepts an explicit `now` parameter (RED asserts this). `activate`/`deactivate` pass `datetime.now(UTC)` via a `_utcnow()` helper. Incoming `valid_from` / `valid_until` datetimes from JSON are parsed as timezone-aware by Pydantic (the DB columns are `timezone=True`). Comparison is between aware datetimes — no naive/aware mixing.
**Why:** The DB column is timestamptz; Python-side comparisons must be aware. Centralizing `_utcnow()` makes it easier to monkeypatch in tests if ever needed (not needed now — RED tests use real time).

### D10 — `_to_response(promo)` helper builds the `PromocodeResponse`

**Decision:** A module-level `_to_response(promo, now=None) -> PromocodeResponse` helper:
- Computes state.
- Constructs `PromocodeResponse.model_validate(promo, from_attributes=True, ...)` plus state override.

Used everywhere the router returns a promo. Avoids duplicating the state-computation call.

### D11 — `main.py` includes the router without a prefix

**Decision:** `admin_promocodes_router` uses `APIRouter(prefix="/api/v1/admin", tags=["admin-promocodes"])` internally (mirrors `admin_orders_router`). `main.py` calls `app.include_router(admin_promocodes_router)` with no additional prefix.
**Why:** Mirrors the existing admin_orders pattern. Keeps path templates in one place (inside the router module) matching RED's matrix assertions literally.

### D12 — RBAC matrix entries placed alongside existing admin rows

**Decision:** Six rows added to `rbac_matrix.py::ROUTE_MATRIX` (in a grouped block with a `# admin-promocodes` comment), each mapped to `{ADMIN}`. No entries added to `PUBLIC_ROUTES`.

## Risks / Trade-offs

- **[Risk]** The middleware-based RBAC check may short-circuit authentication (401) before reaching the route handler, masking 404 cases for unknown ids under customer/barista headers. → **Mitigation:** Not a problem — RED only asserts 403/401 for wrong roles, and 404 only for admin+unknown-id. The two paths don't conflict.
- **[Risk]** In-Python state filter iterates full result set. → **Mitigation:** Promocode count is bounded for MVP. If this becomes hot, a future change can add a CASE-based SQL filter. Out of scope here (YAGNI).
- **[Risk]** `IntegrityError` on duplicate code leaves the session in a failed state. → **Mitigation:** `create_promocode` catches `IntegrityError`, calls `db_session.rollback()`, then raises `PromocodeCodeConflictError`. The router's session is thus clean for subsequent requests.
- **[Risk]** PATCH body with `{"is_active": true}` on an unused promo bypasses the activate/deactivate guards. → **Mitigation:** Intentional. PATCH is a low-level edit; activate/deactivate are the high-level lifecycle entry points with guards. The admin UI SHOULD use activate/deactivate; PATCH is for bulk edits. RED tests do not probe this corner, so GREEN does not add a guard.
- **[Risk]** `created_at` is server-side default (`now()`); tests that set `created_at` via `.update({Promocode.created_at: ...})` may conflict with server default. → **Mitigation:** SQLAlchemy `.update()` with explicit value wins over `server_default`. Already exercised in RED's `test_list_sort_created_at_desc`.
- **[Trade-off]** Domain exceptions + router translation adds ~30 lines vs raising `HTTPException` from the service. Accepted — keeps the service testable without FastAPI.

## 152-FZ Compliance

Promocodes contain no PII (INV-013). `PromocodeUsage` (which has a `user_id` FK) is NOT exposed via this API. `code`, `discount_*`, `valid_*`, `max_uses*`, `current_uses`, `is_active`, `created_at` are all non-personal.

## Atomicity Analysis (INV-004)

- `create_promocode`: single INSERT + COMMIT. `IntegrityError` → `rollback()` + `PromocodeCodeConflictError`. No partial state.
- `update_promocode`: SELECT + (field-lock check: may raise without mutating) + apply patch in-memory + invariant re-check (may raise without persisting — ORM mutation rolled back implicitly by next `rollback()`) + COMMIT. In the field-lock path, no `commit()` is called, so the in-session ORM mutation doesn't matter — the router's surrounding session lifetime rolls back at request-end.

  **Caveat:** because we mutate the ORM instance in step 3 before the invariant check in step 4, if step 4 raises, the session still holds dirty state. We SHALL call `db_session.rollback()` in the service's invariant-check branch before raising to ensure clean state.
- `activate` / `deactivate`: SELECT + compute + guard-or-raise + set `is_active` + COMMIT. Guards fire before mutation. No rollback needed on guard-raise paths.
- `list_promocodes` / `get_promocode`: read-only, no commit.

No cross-row transactions. No coordination with promocode_usages, orders, loyalty, or payments. The checkout-side race (race-fix zone) is untouched.

## State Machine (PDD §6.6)

Implemented transitions:
- `INACTIVE → ACTIVE` via `POST /activate` (guards: valid_until required, not expired, not exhausted).
- `ACTIVE → INACTIVE` via `POST /deactivate` (guard: not expired).
- `INACTIVE → EXPIRED` (computed; no transition action).
- `ACTIVE → EXPIRED` (computed; no transition action).
- `ACTIVE → EXHAUSTED` (computed; no transition action — checkout side drives `current_uses`).
- `EXPIRED → ∅` terminal (guarded by `PromocodeStateConflictError`).

Non-transition behaviors (not state changes):
- PATCH on unused promo mutates any field.
- PATCH on used promo mutates only {valid_until, max_uses, max_uses_per_user, min_order_amount, is_active}.

## Migration Plan

No schema change. Rollback = `git revert` of the GREEN commit.

## Open Questions

None — every decision is pinned by the RED contract.
