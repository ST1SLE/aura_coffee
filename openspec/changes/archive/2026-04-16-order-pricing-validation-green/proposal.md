## Why

The RED cycle (`order-pricing-validation-red`) pinned the contract for five new pure pricing functions in `core_api.services.pricing` and a new `core_api.services.validators` package via 50 failing tests. GREEN now ships the implementation that turns those tests green — unblocking checkout/order creation downstream (PDD §7.2 pricing chain, PDD §7.3–7.5 validators, INV-003/006/008/009/011).

## What Changes

- **Pricing module** (`services/core-api/src/core_api/services/pricing.py`):
  - Add `apply_promocode(subtotal, promocode) -> (discount, after_promo)` — PERCENT/FIXED_AMOUNT branches, floor division, caps at subtotal (PDD §7.2 step 2, INV-011).
  - Add `apply_loyalty_points(after_promo, requested_points, user_balance) -> (points_used, after_points)` — caps at `min(requested, balance, after_promo)` (PDD §7.2 step 3).
  - Add `compute_delivery_fee(subtotal, shop_settings) -> int` — raises `MinimumDeliveryAmountError` below min, returns `0` above `free_delivery_threshold`, otherwise `delivery_fee` (PDD §7.4 step 1, INV-009).
  - Add `compute_order_total(after_points, delivery_fee) -> int` — simple sum (PDD §7.2 step 5).
  - Add `compute_estimated_accrual(after_points, loyalty_percent) -> int` — `floor(after_points × percent / 100)` (INV-003, excludes delivery fee).
  - Preserve purity: no framework imports (existing `test_pricing_module_has_no_framework_imports` must continue passing).
- **New validators package** (`services/core-api/src/core_api/services/validators/`):
  - `exceptions.py`: `ValidationError` base + `StopListError`, `PromocodeValidationError`, `MinimumDeliveryAmountError`, `DeliveryRadiusError`, `TimeSlotValidationError`.
  - `stop_list.py`: `validate_stop_list(cart_items, db_session)` — rereads MenuItem/SizeOption/Modifier from DB, raises `StopListError` on `available=False`, returns validated items with fresh DB prices (INV-006, PDD §7.2 step 1).
  - `working_hours.py`: `validate_time_slot(requested_time, order_type, shop_settings, now=None)` — ASAP + explicit time, prep/delivery-minutes arithmetic, next-opening search ≤24h, raises `TimeSlotValidationError` (PDD §7.5).
  - `delivery.py`: `validate_delivery_address(lat, lon, shop_settings)` Haversine (Earth radius 6371 km) + `validate_min_delivery_amount(subtotal, shop_settings)` (PDD §7.3 step 3, §7.4 step 1, INV-008, INV-009).
  - `promocode.py`: `validate_promocode(code, user_id, subtotal, db_session)` — 7-check chain (code exists, active, valid_from, valid_until, global quota, per-user quota, min_order_amount), returns `Promocode` ORM instance (PDD §5.2, INV-011).
  - `__init__.py`: re-exports the five public validator functions.

## Capabilities

### New Capabilities
<!-- none; this GREEN maps tests-driven contract to implementation -->

### Modified Capabilities
- `order-pricing-validation-tests`: implementation catches up to the RED test file — after GREEN, all RED tests pass and VERIFY scenarios flip from "fails with ImportError" to "passes the post-GREEN assertion".

## Impact

- **Code**: 1 file modified (`pricing.py`), 6 files created (validators package).
- **Tests**: 50 existing RED tests flip to PASS. Existing pricing purity check continues to pass.
- **Dependencies**: None — no new packages. `math` (stdlib) for Haversine; `datetime` (stdlib) for working-hours; SQLAlchemy ORM (already a core-api dep) for stop-list/promocode.
- **Downstream unblocked**: checkout flow can now call the pricing chain + validators (future change will wire the router).

## Non-Goals

- No HTTP router wiring (validators raise domain exceptions; router-layer conversion to HTTPException is a later change).
- No checkout orchestration function (pure pricing + pure validators only).
- No migrations, no seed changes, no model additions.
- No frontend changes, no OpenAPI regeneration (no new HTTP endpoints yet).
- No loyalty-percent cap validation (checkout-level concern).

## MVP Phase

Phase 3 — Order & Payment (prerequisite for checkout endpoint in a later change); relies on Phase 2 Menu & Cart (stop-list) and Phase 5 Loyalty & Promocodes data models already present.
