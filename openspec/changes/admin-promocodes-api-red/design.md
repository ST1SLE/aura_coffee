## Context

Phase 3 seeded the `promocodes` + `promocode_usages` tables (migration 0005) and the customer-side validator `services/validators/promocode.py::validate_promocode` used at checkout. The admin side is completely absent — there is no router, service, or schema for promocode CRUD. The Phase 5 admin UI cannot be built until the backend locks a stable contract.

PDD §6.6 is unusually prescriptive:
- Promocode state is NOT a column; it is computed from `is_active`, `valid_from`, `valid_until`, `max_uses`, `current_uses`, and the current time (INV-011).
- After a promocode has been used at least once (`current_uses > 0`), the fields that shape discount value SHALL be frozen: `code`, `discount_type`, `discount_value`. The rest remain editable.
- Physical `DELETE` is forbidden — "delete" means deactivate. The DB-level FK `promocode_usages.promocode_id → promocodes.id ON DELETE RESTRICT` enforces this.
- From EXPIRED there are no outgoing transitions — expired codes cannot be reactivated.

INV-010 mandates ADMIN-only access for the CRUD surface: BARISTA does not need promocode management (they run the kitchen), COURIER does not see promocodes at all, CUSTOMER redeems via checkout. Any role widening MUST come through a spec delta, not a silent matrix edit.

This RED change is a pure test-authoring change: it locks the HTTP contract, the service API, the schema shapes, and the RBAC matrix for `admin-promocodes-api` before any implementation exists. Per AGENTS.md Two-Change Model, the change MUST end with every new test failing and every pre-existing test still passing.

**Affected modules:** `[core-api]`, `[shared]` (read-only — reuses existing `Promocode` model and `PromocodeDiscountType` enum).

## Goals / Non-Goals

**Goals:**
- Author failing tests that pin every bullet of `admin-promocodes-api` against PDD §3 Promocode, §5.2, §6.6, §7.1 Phase 5 item 1, §7.2 step 2, INV-010, INV-011, INV-004.
- Lock the state-derivation function `compute_state` as the single source of truth for EXPIRED/EXHAUSTED/ACTIVE/INACTIVE semantics — tests pin the priority (EXPIRED beats EXHAUSTED beats ACTIVE; otherwise INACTIVE).
- Lock the CRUD surface: six endpoints under `/api/v1/admin/promocodes` with exact method+path pairs.
- Lock the schema contract: `PromocodeCreate`, `PromocodeUpdate`, `PromocodeResponse` (with computed `state`), `PromocodeListResponse`, `PromocodeState` literal.
- Lock the edit rules: `current_uses=0` → all fields editable; `current_uses>0` → locked fields raise 422 with error code `"field_locked_after_use"` and the offending field name.
- Lock activate/deactivate preconditions: `valid_until` required to activate; EXPIRED cannot activate or deactivate; EXHAUSTED cannot activate.
- Lock the RBAC matrix: all six rows SHALL map to `{ADMIN}` exactly, and NONE SHALL appear in `PUBLIC_ROUTES`.
- Keep the RED signal clean: target-module imports SHALL live inside test bodies so a missing implementation fails per test, not at collection.

**Non-Goals:**
- Writing any service function, router, schema, or `main.py` wiring (GREEN phase).
- Modifying `services/validators/promocode.py` — checkout-side validation chain, zone owned by the race-fix initiative.
- Modifying `services/pricing.py` or `services/checkout.py`.
- Adding any column to `promocodes` (explicitly forbidden by INV-011).
- Adding a DELETE endpoint — archive-style per PDD §6.6.
- Loyalty `ADMIN_ADJUSTMENT` — Phase 6 users-admin.
- Admin frontend — separate web-admin change.
- Analytics / reporting endpoints — promocode usage statistics are out of scope.
- New migrations.

## Decisions

### D1 — New capability `admin-promocodes-api`, not a delta to any existing spec

**Decision:** Introduce `admin-promocodes-api` as a NEW capability.
**Why:** No existing capability covers admin promocode management. `services/validators/promocode.py` is the checkout-side surface and has no spec entry of its own. The admin side has a distinct RBAC row, distinct schemas, and a distinct state machine (§6.6). Folding it under a catch-all "promocodes" spec would require retrofitting; a fresh capability keeps the admin surface reviewable independently.
**Alternative:** Delta on a hypothetical `promocodes` spec. Rejected — no such spec exists.

### D2 — State is a computed function `compute_state(promo, now)`, never a column

**Decision:** The RED tests SHALL assert a pure function `compute_state(promo, now)` in `core_api.services.admin_promocodes` returning `Literal['inactive','active','expired','exhausted']`. The priority SHALL be:
1. `valid_until IS NOT NULL AND now > valid_until` → `expired`
2. else `max_uses IS NOT NULL AND current_uses >= max_uses` → `exhausted`
3. else `is_active AND (valid_from IS NULL OR now >= valid_from)` → `active`
4. else → `inactive`
**Why:** PDD §6.6 and INV-011 forbid a `status` column. A single pure function is the only sane way to guarantee every caller (list, detail, activate guard, deactivate guard) gets identical semantics — regressions in one caller can't drift from the others.
**Alternative:** Compute inline at each call site. Rejected — code duplication + drift risk. Tested via D3.

### D3 — `compute_state` is tested independently of CRUD

**Decision:** RED tests SHALL exercise `compute_state` directly with crafted `Promocode` instances (without persisting them) against a fixed `now`, covering all four branches and priority edges (e.g. `current_uses >= max_uses` AND `now > valid_until` → `expired` wins; active `is_active=false` → `inactive` not `active`).
**Why:** Decoupling the state function from DB fixtures makes the RED report pinpoint which branch regresses in GREEN.

### D4 — Router sits at `core_api.routers.admin_promocodes`, service at `core_api.services.admin_promocodes`

**Decision:** Create two new modules side by side with the existing admin surface: `routers/admin_promocodes.py` with `APIRouter(prefix="/api/v1/admin", tags=["admin-promocodes"])`, and `services/admin_promocodes.py` hosting `compute_state` and the CRUD functions.
**Why:** Mirrors the `admin_orders` layout (router alongside `menu_admin`, service alongside `order_history`). Keeps the checkout-side `validators/promocode.py` strictly separate — two directories, two zones, two review boundaries.
**Alternative:** Hang admin CRUD off the validators module. Rejected — violates zone boundary and bloats the validators file.

### D5 — Tests MUST fail via `ImportError` / `KeyError` / route-absence, not via collection failure

**Decision:** Every RED test SHALL import `compute_state` / CRUD functions / schemas inside the test body. Router tests SHALL probe `app.routes` for the exact path match BEFORE hitting endpoints in other tests; per-endpoint tests SHALL use the live `TestClient` and assert the contract that will pass after GREEN (currently 404 from `TestClient`).
**Why:** Module-level imports of missing symbols abort whole test files. Body-local imports keep RED granular so GREEN flips each test individually.
**Alternative:** Stub empty symbols in `services/admin_promocodes.py` and `schemas/promocode.py`. Rejected — adds implementation scaffolding to RED, blurring the contract.

### D6 — Schema module: `schemas/promocode.py`, reusing `shared.enums.PromocodeDiscountType`

**Decision:** Tests SHALL import `PromocodeCreate`, `PromocodeUpdate`, `PromocodeResponse`, `PromocodeListResponse`, `PromocodeState` from `core_api.schemas.promocode`. Amounts SHALL be integers in kopecks (consistent with `schemas/menu.py` and `schemas/order.py`). `discount_type` SHALL reuse the shared enum.
**Why:** Single source of truth for enums across checkout + admin. Consistent money representation monorepo-wide.

### D7 — `code` canonicalization: server uppercases on input

**Decision:** RED tests SHALL assert that a `POST /api/v1/admin/promocodes` body with `code="welcome10"` results in a persisted row with `code == "WELCOME10"`. A subsequent POST with `code="WELCOME10"` SHALL return 409. The pattern `^[A-Z0-9_-]+$` SHALL be validated AFTER uppercasing — so lowercase letters pass, punctuation fails.
**Why:** Two codes that differ only in case are the same code to users. Server-side canonicalization prevents "welcome10" and "WELCOME10" from both existing and racing each other at checkout.

### D8 — PATCH field-lock semantics: 422 with error code `"field_locked_after_use"`

**Decision:** When `current_uses > 0`, the router SHALL reject a PATCH body containing any of `code`, `discount_type`, `discount_value` with HTTP 422 and a response body shaped roughly as `{"detail": [{"type": "field_locked_after_use", "field": "<name>"}]}` (exact shape pinned by tests — a single locked-field attempt returns a single entry; tests check the `type` and `field` values, not the envelope shape beyond "the payload names the locked field").
**Why:** FastAPI's default 422 is for Pydantic-level validation. Field-lock is a business rule tied to DB state, so it fires server-side AFTER load-by-id. The explicit error code lets the admin UI surface a targeted message instead of "invalid request".
**Alternative:** Return 403. Rejected — 403 is for auth; this is domain-state-dependent request validation. 422 is correct per RFC 9110 §15.5.21.
**Alternative:** Return 409. Rejected — 409 is for conflicting state of the resource itself (exhausted/expired lifecycle); the PATCH is refused before any state change occurs.

### D9 — Activate/deactivate semantics

**Decision:** `POST /{id}/activate`:
1. Load promo; 404 if not found.
2. If `valid_until IS NULL` → 422 `{"detail": "valid_until required"}`.
3. Compute state; if `expired` → 409 `{"detail": "promocode expired"}`.
4. If `exhausted` → 409 `{"detail": "promocode exhausted"}`.
5. Set `is_active=true`; commit; return `PromocodeResponse`.

`POST /{id}/deactivate`:
1. Load promo; 404 if not found.
2. Compute state; if `expired` → 409 `{"detail": "promocode expired"}`.
3. Set `is_active=false`; commit; return `PromocodeResponse`.
**Why:** PDD §6.6 says "EXPIRED → any" is forbidden. Deactivating an expired code is a no-op that hides the real lifecycle from the UI; 409 forces the admin to acknowledge the terminal state. Activating without `valid_until` would create a forever-active code, which is an antipattern (no natural end-of-campaign).
**Alternative:** Make `valid_until` required at creation time. Rejected — it's nullable in the existing schema (migration 0005) and the customer-side validator handles the NULL case gracefully. Pinning it to activation-time preserves existing storage semantics while still guarding the live-use transition.

### D10 — List endpoint: `state` filter + `code` prefix

**Decision:** `GET /api/v1/admin/promocodes`:
- `state`: one of `"inactive"|"active"|"expired"|"exhausted"|"all"`, default `"all"`. Server-side filter computed in-Python after SQL load (simpler than SQL-embedded state derivation; list sizes are bounded by pagination).
- `code`: optional, case-insensitive prefix match (`LOWER(code) LIKE LOWER(:q) || '%'`). Since server stores UPPERCASE, tests SHALL assert that `?code=welc` matches `code=WELCOME10`.
- `page`, `per_page`: default 1/20, `per_page` capped at 100 (422 at 101).
- Sort: `created_at DESC`.
- Response: `PromocodeListResponse { items: list[PromocodeResponse], total_count, page, per_page }` where each item has a `state` field.
**Why:** `state` is derived, so in-Python filter is correct by construction. `code` prefix match matches the admin workflow (typing the first few letters to find a recent campaign). Pagination contract matches the admin-orders convention (20/100).
**Alternative:** Compute `state` in SQL via CASE expression. Rejected — duplicates the Python logic and diverges from `compute_state` as the single source of truth. The N≤100 bound makes the in-Python filter cheap.

### D11 — `total_count` after state filter

**Decision:** `total_count` SHALL reflect the count AFTER the `state` and `code` filters are applied, BEFORE pagination.
**Why:** The admin UI uses `total_count` to compute page count. Counting pre-filter would break the pagination UX.

### D12 — All write operations commit in a single transaction (INV-004)

**Decision:** `create_promocode`, `update_promocode`, `activate`, `deactivate` SHALL each perform exactly one `session.commit()` at the end of their function body. Tests SHALL NOT assert `commit` call counts directly, but SHALL assert the post-condition (row persisted / row rolled back on error) by re-reading the row via a fresh `session.get(...)` after raising.
**Why:** INV-004 mandates atomic writes. A single commit per operation guarantees the caller observes all-or-nothing semantics even if the service function raises mid-flight.

### D13 — RBAC matrix row is part of the RED contract

**Decision:** RED tests SHALL assert all six method+path pairs are present in `ROUTE_MATRIX` mapped to `{ADMIN}` exactly, and ABSENT from `PUBLIC_ROUTES`. Path templates in the matrix SHALL match the router path templates literally (`{promocode_id}` placeholder).
**Why:** INV-010 lives in the matrix; locking the rows at RED catches accidental role widening (e.g. adding BARISTA) or typos (e.g. `{id}` vs `{promocode_id}`) during GREEN.

### D14 — Factory helper: `make_promocode(**overrides)` + `seed_promocodes_across_states(session)`

**Decision:** Extend `services/core-api/tests/_factories/` with:
- `make_promocode(session, *, code=..., ...) -> Promocode` — creates one row with sensible defaults (PERCENT 10, no `valid_until`, `is_active=False`).
- `seed_promocodes_across_states(session, now) -> dict[str, list[uuid.UUID]]` — seeds four buckets (`inactive`, `active`, `expired`, `exhausted`), returns id lists per bucket. Reused by list tests.
**Why:** Keeps the four-state fixture logic out of test bodies and reusable across list-filter, lifecycle, and edit-rule tests.

## Risks / Trade-offs

- **[Risk]** The in-Python state filter ignores rows that are on pages beyond the fetched slice. → **Mitigation:** D10 loads ALL rows, filters, then slices. Size is bounded by real-world promocode count (~dozens); not a scalability concern for MVP.
- **[Risk]** `code` prefix match via `LOWER(...)` misses the unique index. → **Mitigation:** Unique index is on `code` (case-sensitive, but rows are uppercased by D7 canonicalization), so prefix match on an indexed prefix is still efficient for reasonable prefixes. Not a hot path.
- **[Risk]** D8's 422 payload shape is opinionated; GREEN may diverge on envelope. → **Mitigation:** Tests pin the two leaf values (`type == "field_locked_after_use"`, `field == "<name>"`) via `jsonpath`-style lookup, not the full envelope — leaves GREEN a degree of freedom.
- **[Risk]** EXPIRED-cannot-deactivate (D9) surprises admins who want to hide expired codes from the UI. → **Mitigation:** PDD §6.6 is explicit. Expired codes are already filtered from checkout. Admin UI can filter `state=expired` out of the default view without needing to deactivate them.
- **[Risk]** `compute_state` test fixtures drift from real `Promocode` defaults. → **Mitigation:** D14's `make_promocode` helper is the single source of truth for Promocode construction in tests.
- **[Trade-off]** Locking the 422 error code `"field_locked_after_use"` in RED forbids renaming later without a spec delta. Accepted — spec deltas are cheap.

## 152-FZ Compliance

Promocodes are not PII under 152-FZ (INV-013). The endpoints expose no customer identity, no phone, no email. `PromocodeUsage` (which links promocode+user) is NOT surfaced by this CRUD API — it's an internal join table used by checkout-side quota checks. This change is PII-neutral.

## Atomicity Analysis (INV-004)

- `create_promocode`: single INSERT + COMMIT. Unique constraint on `code` produces `IntegrityError` → translated to HTTP 409. No partial state possible.
- `update_promocode`: SELECT (load) + UPDATE + COMMIT. The field-lock check happens in-Python after load; if it fires, the transaction is rolled back (no UPDATE issued). Lock-free — relies on optimistic concurrency via `updated_at` would be over-engineering here; admin edits are rare and race-free.
- `activate` / `deactivate`: SELECT (load) + compute_state + UPDATE `is_active` + COMMIT. Guards are in-Python pre-UPDATE; if they fire, no UPDATE. Idempotent if called twice (toggling is_active between true/false).
- Cross-cutting: none of these operations touch `current_uses`, `promocode_usages`, orders, or loyalty. The checkout-side race (race-fix zone) is completely untouched.

## State Machine (PDD §6.6)

`compute_state` implements the §6.6 state derivation:

```
INACTIVE  ← initial (is_active=false, no timestamp bounds violated)
INACTIVE → ACTIVE    via POST /activate (preconditions in D9)
ACTIVE   → INACTIVE  via POST /deactivate
ACTIVE   → EXHAUSTED (computed; current_uses reaches max_uses)
ACTIVE   → EXPIRED   (computed; now > valid_until)
INACTIVE → EXPIRED   (computed)
INACTIVE → EXHAUSTED (computed; rare but possible if counter set manually)
EXPIRED  → ∅         terminal (no outgoing transitions; INV-016)
EXHAUSTED → ACTIVE   only if max_uses is relaxed via PATCH (current_uses still > 0, but max_uses field is editable even after use)
EXHAUSTED → INACTIVE only if max_uses is relaxed + deactivate
```

RED does not assert the `EXHAUSTED → ACTIVE` via max_uses-relax transition (it's a consequence of D2 + D9, and tests should not over-specify incidental behavior). GREEN SHALL implement compute_state such that this transition Just Works.

## Migration Plan

No schema change, no data migration. The `promocodes` and `promocode_usages` tables already exist (migration 0005_phase3_schema.py). Rollback of this RED change: `git revert` — no data to reverse.

## Open Questions

- **PATCH error envelope exact shape**: tests pin leaf values only; GREEN has freedom on whether it returns `{"detail": [{"type": "...", "field": "..."}]}` or a flatter shape. If GREEN decides on the flatter shape, `list.json()["detail"]["field"]` is the assertion; if FastAPI-style, `detail[0]["field"]`. RED tests SHALL probe both shapes (try the list-of-dicts path first, fall back to the dict path) to avoid over-specifying. — **Resolution deferred to GREEN.**
- **`code` canonicalization placement**: server-side UPPER() on input (D7) is pinned. Whether this lives in the Pydantic `field_validator` or in the service function is an implementation detail not tested.
- **Empty PATCH body**: behavior when PATCH body is `{}` — returns 200 with unchanged promo? 422? RED tests SHALL NOT assert; GREEN picks.
