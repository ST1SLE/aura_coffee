## 1. Test module scaffolding

- [x] 1.1 [core-api] PREREQ: create empty test module `services/core-api/tests/test_pricing_chain.py` with module docstring describing the RED contract (covers PDD §7.2 steps 2–6, INV-003, INV-011) and imports `ast`, `pathlib`, `pytest`, `types.SimpleNamespace as Ns` at module level. No top-level import from `core_api.services.pricing` (target lives inside each test body — import-time errors must surface per-test).
- [x] 1.2 [core-api] PREREQ: create empty test module `services/core-api/tests/test_validators_stop_list.py` with module docstring (PDD §7.2 step 1, INV-006), imports `pytest`, `uuid`. No top-level import from `core_api.services.validators`. The file uses `migrated_db_session` fixture from `tests.conftest`.
- [x] 1.3 [core-api] PREREQ: create empty test module `services/core-api/tests/test_validators_working_hours.py` with module docstring (PDD §7.5, INV-007), imports `pytest`, `datetime`, `UTC`, `types.SimpleNamespace as Ns`, `shared.enums.OrderType`. No top-level import from `core_api.services.validators`. Time is injected via explicit `now=` argument (no freezegun — not in dev deps).
- [x] 1.4 [core-api] PREREQ: create empty test module `services/core-api/tests/test_validators_delivery.py` with module docstring (PDD §7.3 step 3, §7.4 step 1, INV-008, INV-009), imports `pytest`, `types.SimpleNamespace as Ns`. No top-level import from `core_api.services.validators`.
- [x] 1.5 [core-api] PREREQ: create empty test module `services/core-api/tests/test_validators_promocode.py` with module docstring (PDD §5.2 Промокоды, INV-011), imports `pytest`, `uuid`, `datetime`, `shared.enums.PromocodeDiscountType`. Uses `migrated_db_session` fixture.
- [x] 1.6 [core-api] PREREQ: create empty test module `services/core-api/tests/test_validators_init.py` with module docstring (smoke test for the validators package public surface), imports `pytest`.

## 2. RED: pricing chain — apply_promocode

- [x] 2.1 [core-api] RED: add `test_apply_promocode_none_returns_zero_and_subtotal` to `test_pricing_chain.py` — imports `apply_promocode` from `core_api.services.pricing` inside the body, asserts `apply_promocode(100000, None) == (0, 100000)`. MUST fail with `ImportError`.
- [x] 2.2 [core-api] RED: add `test_apply_promocode_percent_floor_division` — constructs `Ns(discount_type=PromocodeDiscountType.PERCENT, discount_value=10)`, asserts `apply_promocode(30333, promo) == (3033, 27300)` (floor(30333×10/100)=3033). MUST fail.
- [x] 2.3 [core-api] RED: add `test_apply_promocode_percent_zero_value_yields_zero_discount` — `Ns(discount_type=PERCENT, discount_value=0)`, asserts `apply_promocode(50000, promo) == (0, 50000)`. MUST fail.
- [x] 2.4 [core-api] RED: add `test_apply_promocode_fixed_amount_within_subtotal` — `Ns(discount_type=FIXED_AMOUNT, discount_value=5000)`, asserts `apply_promocode(30000, promo) == (5000, 25000)`. MUST fail.
- [x] 2.5 [core-api] RED: add `test_apply_promocode_fixed_amount_caps_at_subtotal` — `Ns(discount_type=FIXED_AMOUNT, discount_value=100000)`, asserts `apply_promocode(30000, promo) == (30000, 0)`. MUST fail.

## 3. RED: pricing chain — apply_loyalty_points

- [x] 3.1 [core-api] RED: add `test_apply_loyalty_points_no_request_returns_zero` — asserts `apply_loyalty_points(after_promo=20000, requested_points=0, user_balance=50000) == (0, 20000)`. MUST fail.
- [x] 3.2 [core-api] RED: add `test_apply_loyalty_points_request_below_balance_and_after_promo` — asserts `apply_loyalty_points(after_promo=20000, requested_points=5000, user_balance=50000) == (5000, 15000)`. MUST fail.
- [x] 3.3 [core-api] RED: add `test_apply_loyalty_points_request_exceeds_balance_uses_balance` — asserts `apply_loyalty_points(after_promo=20000, requested_points=50000, user_balance=15000) == (15000, 5000)`; NO exception raised even though requested > balance. MUST fail.
- [x] 3.4 [core-api] RED: add `test_apply_loyalty_points_cap_at_after_promo` — asserts `apply_loyalty_points(after_promo=10000, requested_points=50000, user_balance=50000) == (10000, 0)`. MUST fail.
- [x] 3.5 [core-api] RED: add `test_apply_loyalty_points_zero_balance` — asserts `apply_loyalty_points(after_promo=20000, requested_points=5000, user_balance=0) == (0, 20000)`. MUST fail.

## 4. RED: pricing chain — delivery / total / accrual

- [x] 4.1 [core-api] RED: add `test_compute_delivery_fee_below_min_raises` — constructs `Ns(min_delivery_amount=50000, free_delivery_threshold=150000, delivery_fee=20000)`, asserts `compute_delivery_fee(40000, shop) raises MinimumDeliveryAmountError` (imported from `core_api.services.validators.exceptions`). MUST fail with `ImportError`.
- [x] 4.2 [core-api] RED: add `test_compute_delivery_fee_equal_to_min_returns_delivery_fee` — asserts `compute_delivery_fee(50000, shop) == 20000`. MUST fail.
- [x] 4.3 [core-api] RED: add `test_compute_delivery_fee_above_free_threshold_returns_zero` — asserts `compute_delivery_fee(200000, shop) == 0`. MUST fail.
- [x] 4.4 [core-api] RED: add `test_compute_delivery_fee_between_min_and_threshold_returns_fee` — asserts `compute_delivery_fee(100000, shop) == 20000`. MUST fail.
- [x] 4.5 [core-api] RED: add `test_compute_order_total_sums_after_points_and_delivery` — asserts `compute_order_total(after_points=12345, delivery_fee=20000) == 32345`. MUST fail.
- [x] 4.6 [core-api] RED: add `test_compute_order_total_zero_delivery_for_pickup` — asserts `compute_order_total(after_points=12345, delivery_fee=0) == 12345`. MUST fail.
- [x] 4.7 [core-api] RED: add `test_compute_estimated_accrual_floor_division` — asserts `compute_estimated_accrual(after_points=10050, loyalty_percent=5) == 502` (INV-003). MUST fail.
- [x] 4.8 [core-api] RED: add `test_compute_estimated_accrual_zero_when_fully_points_paid` — asserts `compute_estimated_accrual(after_points=0, loyalty_percent=5) == 0`. MUST fail.
- [x] 4.9 [core-api] RED: add `test_compute_estimated_accrual_zero_loyalty_percent` — asserts `compute_estimated_accrual(after_points=10000, loyalty_percent=0) == 0`. MUST fail.

## 5. RED: stop_list validator

- [x] 5.1 [core-api] RED: add `test_validate_stop_list_all_available_returns_validated_items` to `test_validators_stop_list.py` — seeds a MenuItem with `available=True`, constructs a plausible cart_items list, imports `validate_stop_list` from `core_api.services.validators`, asserts the returned list has length equal to cart_items and returns MenuItem's fresh `base_price`. MUST fail with `ImportError`.
- [x] 5.2 [core-api] RED: add `test_validate_stop_list_menu_item_unavailable_raises` — seeds MenuItem with `available=False`, asserts `validate_stop_list(...)` raises `StopListError` (from `core_api.services.validators.exceptions`). MUST fail.
- [x] 5.3 [core-api] RED: add `test_validate_stop_list_size_option_unavailable_raises` — seeds MenuItem `available=True` but its SizeOption `available=False`; cart references that size. Asserts `StopListError`. MUST fail.
- [x] 5.4 [core-api] RED: add `test_validate_stop_list_modifier_unavailable_raises` — seeds Modifier `available=False`, cart references it. Asserts `StopListError`. MUST fail.
- [x] 5.5 [core-api] RED: add `test_validate_stop_list_returns_fresh_prices_not_client_prices` — seeds MenuItem with `base_price=25000`; cart carries stale `unit_price=20000`. Asserts the returned validated item exposes the DB price (`25000`). MUST fail.
- [x] 5.6 [core-api] RED: add `test_validate_stop_list_error_carries_offending_item_id` — asserts `StopListError` raised for unavailable item has attribute `.item_id` (or `.menu_item_id`) matching the seeded unavailable MenuItem's id. MUST fail.

## 6. RED: working_hours validator

- [x] 6.1 [core-api] RED: add `test_validate_time_slot_asap_pickup_in_working_hours` to `test_validators_working_hours.py` — `now=datetime("2026-04-16 10:00:00")`, constructs `Ns(working_hours={"thu":{"open":"08:00","close":"22:00"}}, default_prep_time_minutes=15, estimated_delivery_time_minutes=30)`. Imports `validate_time_slot`, asserts return == `datetime(2026,4,16,10,15,0, tzinfo=UTC)`. MUST fail with `ImportError`.
- [x] 6.2 [core-api] RED: add `test_validate_time_slot_asap_delivery_adds_estimated_delivery_time` — same setup but `order_type=OrderType.DELIVERY`. Asserts return == `10:45 UTC`. MUST fail.
- [x] 6.3 [core-api] RED: add `test_validate_time_slot_asap_closed_opens_same_day` — freeze at `02:00 UTC`, working_hours open at 08:00. Asserts return == `08:15 UTC`. MUST fail.
- [x] 6.4 [core-api] RED: add `test_validate_time_slot_asap_closed_gt_24h_raises` — working_hours config has closed days spanning >24h; asserts `TimeSlotValidationError`. MUST fail.
- [x] 6.5 [core-api] RED: add `test_validate_time_slot_explicit_in_past_raises` — freeze at `10:00`, pass `requested_time = 09:00`. Asserts `TimeSlotValidationError`. MUST fail.
- [x] 6.6 [core-api] RED: add `test_validate_time_slot_explicit_below_prep_time_raises` — freeze at `10:00`, prep=15, pass `requested_time = 10:10`. Asserts `TimeSlotValidationError`. MUST fail.
- [x] 6.7 [core-api] RED: add `test_validate_time_slot_explicit_outside_hours_raises` — working_hours 08:00–22:00, pass `requested_time = 23:00`. Asserts `TimeSlotValidationError`. MUST fail.
- [x] 6.8 [core-api] RED: add `test_validate_time_slot_explicit_in_hours_accepts` — freeze at `10:00`, pass `requested_time = 14:00`. Asserts return == `14:00 UTC` unchanged. MUST fail.

## 7. RED: delivery validators

- [x] 7.1 [core-api] RED: add `test_validate_delivery_address_inside_radius_accepts` to `test_validators_delivery.py` — `Ns(shop_lat=55.7558, shop_lon=37.6173, delivery_radius_km=5.0)`. Imports `validate_delivery_address`. Calls with `(55.7600, 37.6200, shop)`. Asserts no exception (returns `None`). MUST fail with `ImportError`.
- [x] 7.2 [core-api] RED: add `test_validate_delivery_address_outside_radius_raises` — same shop, address `(55.9000, 37.6173)`. Asserts `DeliveryRadiusError` (from `...validators.exceptions`). MUST fail.
- [x] 7.3 [core-api] RED: add `test_validate_delivery_address_earth_radius_6371_sanity` — calls with shop coords themselves `(55.7558, 37.6173)`. Asserts no exception (distance=0). MUST fail.
- [x] 7.4 [core-api] RED: add `test_validate_min_delivery_amount_below_raises` — `Ns(min_delivery_amount=50000)`. Imports `validate_min_delivery_amount`. Asserts `validate_min_delivery_amount(40000, shop)` raises `MinimumDeliveryAmountError`. MUST fail.
- [x] 7.5 [core-api] RED: add `test_validate_min_delivery_amount_equal_accepts` — asserts `validate_min_delivery_amount(50000, shop)` returns `None`. MUST fail.
- [x] 7.6 [core-api] RED: add `test_validate_min_delivery_amount_above_accepts` — asserts `validate_min_delivery_amount(200000, shop)` returns `None`. MUST fail.

## 8. RED: promocode validator

- [x] 8.1 [core-api] RED: add `test_validate_promocode_unknown_code_raises` to `test_validators_promocode.py` — no rows seeded. Imports `validate_promocode`. Asserts `validate_promocode("WRONG", uuid.uuid4(), 100000, session)` raises `PromocodeValidationError`. MUST fail with `ImportError`.
- [x] 8.2 [core-api] RED: add `test_validate_promocode_inactive_raises` — seeds row with `is_active=False`. Asserts `PromocodeValidationError`. MUST fail.
- [x] 8.3 [core-api] RED: add `test_validate_promocode_valid_from_future_raises` — seeds row with `valid_from = now + 1h`. Asserts `PromocodeValidationError`. MUST fail.
- [x] 8.4 [core-api] RED: add `test_validate_promocode_valid_until_past_raises` — seeds row with `valid_until = now - 1h`. Asserts `PromocodeValidationError`. MUST fail.
- [x] 8.5 [core-api] RED: add `test_validate_promocode_global_quota_exhausted_raises` — seeds `max_uses=5`, `current_uses=5`. Asserts `PromocodeValidationError`. MUST fail.
- [x] 8.6 [core-api] RED: add `test_validate_promocode_per_user_quota_exhausted_raises` — seeds `max_uses_per_user=2` and inserts 2 `PromocodeUsage` rows for `(user_id, promocode_id)`. Asserts `PromocodeValidationError`. MUST fail.
- [x] 8.7 [core-api] RED: add `test_validate_promocode_subtotal_below_min_order_amount_raises` — seeds `min_order_amount=150000`. Asserts `validate_promocode(code, user, 100000, session)` raises. MUST fail.
- [x] 8.8 [core-api] RED: add `test_validate_promocode_happy_path_returns_promocode` — seeds a fully-valid row. Asserts the returned object has attribute `.code == "<code>"` and `.discount_value` matches. MUST fail.

## 9. RED: package-init smoke test

- [x] 9.1 [core-api] RED: add `test_validators_package_exports_public_names` to `test_validators_init.py` — executes `from core_api.services.validators import validate_stop_list, validate_time_slot, validate_delivery_address, validate_min_delivery_amount, validate_promocode`. Asserts each is `callable`. MUST fail with `ImportError`.
- [x] 9.2 [core-api] RED: add `test_validators_exceptions_module_exports_error_classes` — executes `from core_api.services.validators.exceptions import StopListError, PromocodeValidationError, MinimumDeliveryAmountError, DeliveryRadiusError, TimeSlotValidationError`. Asserts each is a subclass of `Exception`. MUST fail with `ImportError`.
- [x] 9.3 [core-api] RED: add `test_validators_exceptions_share_base_class` — asserts `issubclass(StopListError, ValidationError)` etc. — expects a small `ValidationError` base class in the same module. MUST fail.

## 10. VERIFY (RED)

- [x] 10.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_pricing_chain.py services/core-api/tests/test_validators_stop_list.py services/core-api/tests/test_validators_working_hours.py services/core-api/tests/test_validators_delivery.py services/core-api/tests/test_validators_promocode.py services/core-api/tests/test_validators_init.py -v`; confirm every new test FAILS (no accidental passes). Record the count of failing tests in the task completion note.
- [x] 10.2 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/ --ignore=services/core-api/tests/test_pricing_chain.py --ignore=services/core-api/tests/test_validators_stop_list.py --ignore=services/core-api/tests/test_validators_working_hours.py --ignore=services/core-api/tests/test_validators_delivery.py --ignore=services/core-api/tests/test_validators_promocode.py --ignore=services/core-api/tests/test_validators_init.py -v`; confirm no pre-existing test regresses.
