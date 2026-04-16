## Context

Affected modules: `[core-api]`.

Phase 3 Order & Payment (PDD §7.1) has landed the schema (Order, OrderItem, Payment, Promocode, PromocodeUsage, LoyaltyAccount, LoyaltyTransaction, ShopSettings — see `packages/shared/src/shared/models/`). The checkout endpoint needs business-logic glue between Cart → Order:

- The existing `core_api.services.pricing` module covers only PDD §7.2 **step 1** (subtotal via `compute_line_total` / `compute_subtotal`). Steps 2–6 (promo discount, point redemption, delivery fee, total, estimated accrual) are missing.
- There is no `validators/` package yet. Stop-list validation (INV-006), working-hours/time-slot validation (INV-007, §7.5), delivery radius (INV-008, §7.3 step 3), minimum delivery amount (INV-009, §7.4 step 1), and promocode validity (§5.2 + INV-011) are each required pre-checkout guards and ship collectively here.

Per the "Two-Change Model" in `AGENTS.md`, this change is the **RED** cycle: it ships only failing tests that pin the contract. Code lands in the sibling change `order-pricing-validation-green`.

Existing reference: `services/core-api/tests/test_pricing.py` (Phase-2 pricing contract, 13 tests) and the import-purity AST check in that file.

## Goals / Non-Goals

**Goals:**
- Ship a test suite that fully pins the signature, return shape, and exception behavior of every new pricing function and every new validator.
- Keep pricing.py's pure-function contract auditable (AST import check extended to the new file — rather, the existing check on pricing.py is preserved in RED; no new purity check is needed because no new module is edited).
- Keep tests unit-level: pricing tests use plain ints and dataclasses/SimpleNamespace for `Promocode` / `ShopSettings` stand-ins so the pure functions stay DB-free. Validators that genuinely need DB (`validate_stop_list`, `validate_promocode`) use the existing `migrated_db_session` fixture from `conftest.py`.
- Make every assertion derive from a PDD clause or INV-XXX, cited in each test's docstring.

**Non-Goals:**
- No production code — RED ships tests only.
- No router-layer wiring, no HTTP-error translation, no middleware.
- No end-to-end checkout integration tests.
- No amendments to existing tests (`test_pricing.py` stays untouched).
- No changes to `order-schema` or `order-schema-tests` specs.

## Decisions

### D1. Validators live in a new package `core_api.services.validators`, not in `services/validators.py`.

**Why:** The five validators split naturally by concern (stop-list / time / delivery / promocode / package `__init__`). A package keeps each file under ~150 LOC and matches the pattern used elsewhere in `core_api.services` (one file per concern — `auth.py`, `cart.py`, `otp.py`, etc.).

**Alternative considered:** A single `validators.py`. Rejected because it muddles four unrelated PDD chains (§7.2 stop-list, §7.5 time, §7.3/§7.4 delivery, §5.2 promocode) under one module.

### D2. Validators raise domain exceptions, not `HTTPException`.

**Why:** Keeps the service layer framework-agnostic (same rule applies to `pricing.py` — it raises `ValueError`). The router layer (later change) maps each exception to a 400/422 with a bilingual user-facing message. Tests assert on exception class, not on HTTP status.

**Classes introduced (in `validators/exceptions.py`, shipped by GREEN; referenced by name in RED tests):**
- `StopListError` — `validate_stop_list` rejects when any MenuItem / SizeOption / Modifier has `available=False`.
- `PromocodeValidationError` — `validate_promocode` rejects when the promocode fails any of: `is_active`, window, global/per-user quota, min_order_amount.
- `MinimumDeliveryAmountError` — `validate_min_delivery_amount` rejects when `subtotal < min_delivery_amount`.
- `DeliveryRadiusError` — `validate_delivery_address` rejects when `haversine(shop, address) > delivery_radius_km`.
- `TimeSlotValidationError` — `validate_time_slot` rejects when requested/ASAP time cannot be satisfied within 24h or working hours.

All inherit from a small `ValidationError` base class in the same file to allow `except ValidationError` catch-alls in the router.

### D3. Pricing extensions stay pure; framework-free.

**Why:** Same rationale that drove the existing `pricing.py` (see its module docstring). Pure integer functions are easy to test, easy to reuse in admin tooling, and avoid fan-out of SQLAlchemy into checkout.

**How tests express this:** Pricing tests accept `Promocode` / `ShopSettings` models — but the functions only read a handful of attributes (`discount_type`, `discount_value`, `min_delivery_amount`, `free_delivery_threshold`, `delivery_fee`). RED tests pass a `SimpleNamespace` with just those attributes so the pricing module does not have to import the SQLAlchemy model. The existing AST import-check in `test_pricing.py` is left unchanged — it already covers any future edits to `pricing.py`.

### D4. Validator fixtures — DB vs pure.

- `validate_stop_list` and `validate_promocode` **require DB access** (to look up fresh `MenuItem`/`SizeOption`/`Modifier` state per INV-006, and to read `Promocode` + count rows in `promocode_usages`). Their RED tests use `migrated_db_session` and the existing seed/factory machinery in `tests/_factories/`.
- `validate_time_slot`, `validate_delivery_address`, `validate_min_delivery_amount` are **pure**. They take already-loaded `ShopSettings` plus scalar arguments, so their tests construct a `SimpleNamespace` (or a detached `ShopSettings` instance) and need no DB. For time, the validator accepts an optional `now: datetime | None = None` parameter — `None` means "real now via `datetime.now(UTC)`". Tests pass explicit `now` to avoid the `freezegun` dependency (not in project `pyproject.toml`).

### D5. `validate_stop_list` returns "validated items with fresh prices", not just raises.

**Why:** PDD §7.2 step 1 says "все цены берутся из БД на момент расчёта (не из кэша клиента)". The validator is the canonical source of fresh prices; the checkout service uses the returned list to build `line_total`s and ultimately `OrderItem` snapshots. A pure `raise-only` shape would force the caller to re-query. Tests assert both the raise path (INV-006) and the return shape.

### D6. `validate_time_slot` returns `estimated_ready_at`.

**Why:** PDD §7.5 step 2 computes this value; persisting it avoids re-deriving it when writing the `Order` row. Tests assert return value for every branch (ASAP in-hours, ASAP next-open ≤24h, explicit time in-hours).

### D7. Haversine uses Earth radius = 6371 km (PDD-specified).

**Why:** PDD §7.3 step 3 pins the formula and constant. Tests use a small tolerance (≤10 m) to avoid float flakiness and verify the constant by checking a known reference pair (e.g. shop vs self → ~0).

### D8. `ShopSettings` stand-in: use `SimpleNamespace`, not a raw dict.

**Why:** Callers in the GREEN cycle will receive a real `ShopSettings` ORM instance. Attribute access (`.min_delivery_amount`) is the runtime contract; a dict would silently pass in tests but fail in production. `SimpleNamespace` is the cheapest fixture that preserves attribute-access semantics.

## Risks / Trade-offs

- **[Risk]** Tests that exercise `validate_time_slot` at working-hours boundaries are timezone-sensitive.
  **Mitigation:** The validator accepts an optional `now: datetime | None` parameter (clock injection). Tests pass an explicit `now` with `tzinfo=UTC`, and the stand-in `ShopSettings.working_hours` uses explicit strings ("08:00"/"22:00") interpreted as UTC for the RED contract. The GREEN implementation may later consult a shop timezone; that refinement is out of scope for RED.
- **[Risk]** `validate_promocode` needs a user-usage count; querying `promocode_usages` per-test is slow.
  **Mitigation:** Use the existing `migrated_db_session` scope and a dedicated minimal factory for `Promocode` + `PromocodeUsage`. Tests seed 0/1/many usage rows per case.
- **[Risk]** Test count balloons (≥40 cases) and RED runs slow.
  **Mitigation:** Pricing tests (~18) are pure/fast. DB-backed validator tests (stop-list ~5, promocode ~8) reuse a single `migrated_db_session` scope. Total RED runtime budget: <10s on CI.
- **[Trade-off]** Choosing `SimpleNamespace` stand-ins over real ORM instances in pure tests means the GREEN code must tolerate `Mapping`-like ORM access. All existing ORM columns already use `Mapped[...]` so attribute access works identically — no observable difference.

## Atomicity Analysis (INV-004)

This change ships validators only — no DB writes, no YuKassa calls, no loyalty ledger entries. INV-004 atomicity will be exercised by the later checkout-endpoint change when `validate_promocode`, `apply_loyalty_points`, and `compute_order_total` are called inside a single DB transaction together with `Order` creation, `PromocodeUsage` insertion, `LoyaltyTransaction` insertion, and YuKassa Payment creation. RED tests for that transaction are **out of scope** for this change.

## Migration Plan

- No DB migrations. No schema changes. No seed changes.
- Forward deploy: merge the RED change → test suite grows with failing tests → GREEN change merges behind it on the same feature branch.
- Rollback: remove the six new test files. No production side effects to roll back.

## 152-FZ Compliance (INV-013)

No PII is introduced or touched. Validators operate on `user_id` (opaque UUID), scalar prices, timestamps, lat/lon pairs, and `Promocode` / `ShopSettings` rows — none of which store PII. Unaffected.

## Open Questions

None. All test signatures and branches are derivable from PDD §7.2–§7.5 + INV-003/006/009/011 + existing `ShopSettings` / `Promocode` models.
