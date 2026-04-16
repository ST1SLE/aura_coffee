## Why

Phase 3 (Order & Payment) needs a pricing chain beyond the subtotal (already in `pricing.py`) and a full set of pre-checkout validators (stop-list, working hours, delivery radius, minimum delivery amount, promocode). PDD §7.2 (steps 2–6), §7.3 (step 3), §7.4, §7.5 and invariants INV-003, INV-006, INV-009, INV-011 define the contract. TDD discipline (per `AGENTS.md` "Two-Change Model") requires the contract to be pinned as failing tests BEFORE implementation, so this RED change ships tests only — the sibling `order-pricing-validation-green` change delivers code.

## What Changes

- Add `services/core-api/tests/test_pricing_chain.py` — unit tests for new pure pricing functions (`apply_promocode`, `apply_loyalty_points`, `compute_delivery_fee`, `compute_order_total`, `compute_estimated_accrual`), plus an AST-based import-purity check mirroring the existing pattern in `test_pricing.py`.
- Add `services/core-api/tests/test_validators_stop_list.py` — tests for `validate_stop_list` (INV-006, §7.2 step 1): unavailable MenuItem/SizeOption/Modifier rejection, price-freshness contract.
- Add `services/core-api/tests/test_validators_working_hours.py` — tests for `validate_time_slot` (§7.5): ASAP happy path, ASAP while closed (next opening within 24h), ASAP while closed >24h (reject), explicit time in past, below prep-time, outside working hours, DELIVERY adds estimated delivery time.
- Add `services/core-api/tests/test_validators_delivery.py` — tests for `validate_delivery_address` (§7.3 step 3, INV-008; Haversine with Earth radius 6371 km) and `validate_min_delivery_amount` (§7.4 step 1, INV-009).
- Add `services/core-api/tests/test_validators_promocode.py` — tests for `validate_promocode` (PDD §5.2 promocode rules): is_active, valid_from/valid_until window, current_uses < max_uses, per-user usage count from `promocode_usages`, subtotal ≥ min_order_amount.
- Add `services/core-api/tests/test_validators_init.py` — smoke test that `from core_api.services.validators import validate_stop_list, validate_time_slot, validate_delivery_address, validate_min_delivery_amount, validate_promocode` works and the package is importable.
- All new tests are expected to FAIL with `ImportError`/`AttributeError` until the GREEN cycle lands the pricing functions, the `validators/` package, and the `validators/exceptions.py` module with the domain exception classes (`StopListError`, `PromocodeValidationError`, `MinimumDeliveryAmountError`, `DeliveryRadiusError`, `TimeSlotValidationError`).

## Capabilities

### New Capabilities
- `order-pricing-validation-tests`: RED-cycle test suite that pins the contract for the pricing-chain extensions (`pricing.py`) and the new `services/validators/` package. Lives entirely in `services/core-api/tests/`. Covers PDD §7.2 (steps 2–6), §7.3 (step 3), §7.4, §7.5 and invariants INV-003, INV-006, INV-009, INV-011. No production code is shipped in this change.

### Modified Capabilities
<!-- None — the existing `pricing` capability's current behavior (compute_line_total, compute_subtotal) is unchanged. The GREEN cycle will extend it and may amend the `pricing` capability spec. -->

## Impact

- Affected code: `services/core-api/tests/` (six new test files).
- Affected tooling: `pytest` test suite will gain ~40 failing tests (expected during RED).
- Affected dependencies: none — uses existing pytest + SQLAlchemy + Pydantic + freezegun fixtures already available in conftest.
- Not affected in this cycle: production code under `services/core-api/src/core_api/services/` (no edits to `pricing.py`, no new `validators/` package), no migrations, no seeds, no schemas, no routers, no frontend.

## MVP Phase

- Phase 3: Order & Payment (PDD §7.1). Unlocks checkout endpoint work in subsequent features.

## Non-Goals

- No production code changes (no new pricing functions, no `validators/` package, no `exceptions.py`).
- No router wiring or HTTP-error conversion — validators raise domain exceptions; router translation is a later change.
- No integration tests covering the full checkout flow end-to-end. Tests are unit-level against the validator / pricing function signatures.
- No changes to `order-schema`, `cart-schema`, or any migrations.
- No frontend work (customer/admin SPAs).
- No YuKassa, SMS, or Yandex.Maps integrations — validators are self-contained.
- No loyalty accrual application (the `COMPLETED`→accrual transaction lives in order-lifecycle work); this change only covers `estimated_accrual` computation per INV-003.
