## ADDED Requirements

### Requirement: RED test file for pricing-chain extensions

**References PDD §7.2 (steps 2–6), INV-003, INV-011.**

The RED cycle SHALL ship `services/core-api/tests/test_pricing_chain.py` with unit tests that fail on the current codebase and pin the contract for five new pure functions in `core_api.services.pricing`: `apply_promocode`, `apply_loyalty_points`, `compute_delivery_fee`, `compute_order_total`, `compute_estimated_accrual`. Tests MUST use plain integers (kopecks) and `SimpleNamespace` stand-ins for `Promocode` and `ShopSettings`.

#### Scenario: apply_promocode — None returns (0, subtotal)

- **WHEN** the test calls `apply_promocode(subtotal=100000, promocode=None)` before GREEN is merged
- **THEN** the import of `apply_promocode` from `core_api.services.pricing` raises `ImportError`

#### Scenario: apply_promocode — PERCENT applies floor(subtotal × value / 100)

- **WHEN** the test calls `apply_promocode(subtotal=30333, promocode=Ns(discount_type=PERCENT, discount_value=10))`
- **THEN** the symbol is absent, the import fails, and the assertion on the tuple `(3033, 27300)` is never reached

#### Scenario: apply_promocode — FIXED_AMOUNT caps at subtotal

- **WHEN** the test asserts `apply_promocode(subtotal=5000, promocode=Ns(discount_type=FIXED_AMOUNT, discount_value=10000))` returns `(5000, 0)`
- **THEN** the function symbol is missing, the test fails with `ImportError`

#### Scenario: apply_loyalty_points — requested > balance uses entire balance

- **WHEN** the test calls `apply_loyalty_points(after_promo=20000, requested_points=50000, user_balance=15000)`
- **THEN** the import/function lookup fails; post-GREEN the call MUST return `(15000, 5000)` — no exception even though requested > balance

#### Scenario: apply_loyalty_points — redeemable cap at after_promo

- **WHEN** the test calls `apply_loyalty_points(after_promo=10000, requested_points=50000, user_balance=50000)`
- **THEN** post-GREEN the call MUST return `(10000, 0)`; in RED the symbol is missing

#### Scenario: compute_delivery_fee — subtotal below min raises

- **WHEN** the test calls `compute_delivery_fee(subtotal=40000, shop_settings=Ns(min_delivery_amount=50000, free_delivery_threshold=150000, delivery_fee=20000))`
- **THEN** post-GREEN the call MUST raise `MinimumDeliveryAmountError`; in RED `compute_delivery_fee` does not exist

#### Scenario: compute_delivery_fee — free over threshold

- **WHEN** the test calls `compute_delivery_fee(subtotal=200000, shop_settings=Ns(min_delivery_amount=50000, free_delivery_threshold=150000, delivery_fee=20000))`
- **THEN** post-GREEN the return is `0`

#### Scenario: compute_delivery_fee — paid between min and threshold

- **WHEN** the test calls `compute_delivery_fee(subtotal=100000, shop_settings=Ns(min_delivery_amount=50000, free_delivery_threshold=150000, delivery_fee=20000))`
- **THEN** post-GREEN the return is `20000`

#### Scenario: compute_order_total sums after_points + delivery_fee

- **WHEN** the test calls `compute_order_total(after_points=12345, delivery_fee=20000)`
- **THEN** post-GREEN the return is `32345`

#### Scenario: compute_estimated_accrual — INV-003 excludes delivery_fee

- **WHEN** the test calls `compute_estimated_accrual(after_points=10050, loyalty_percent=5)` (after_points is the goods portion, not the delivery fee)
- **THEN** post-GREEN the return is `floor(10050 × 5 / 100) = 502`

#### Scenario: compute_estimated_accrual — zero after 100% points redemption

- **WHEN** the test calls `compute_estimated_accrual(after_points=0, loyalty_percent=5)`
- **THEN** post-GREEN the return is `0` (INV-003: no accrual on fully points-paid portion)

#### Scenario: pricing module remains framework-free

- **WHEN** `test_pricing.py::test_pricing_module_has_no_framework_imports` is re-run after GREEN
- **THEN** `pricing.py` MUST NOT import `sqlalchemy`, `redis`, `fastapi`, `pydantic`, `core_api.models`, or `shared.models`

---

### Requirement: RED test file for stop-list validator

**References PDD §7.2 step 1, INV-006.**

The RED cycle SHALL ship `services/core-api/tests/test_validators_stop_list.py` with tests that pin the `validate_stop_list(cart_items, db_session)` contract. Tests MUST use `migrated_db_session` and the existing menu factories.

#### Scenario: all items available — returns validated items with fresh DB prices

- **WHEN** a cart references a MenuItem with `available=True` and the test calls `validate_stop_list(cart_items, session)`
- **THEN** post-GREEN the call returns a list of dicts/records whose `unit_price` reflects the current DB value (not the client-supplied value); in RED the import fails

#### Scenario: MenuItem in stop-list raises StopListError

- **WHEN** a cart references a MenuItem with `available=False`
- **THEN** post-GREEN `validate_stop_list` raises `StopListError`; the error SHALL carry the offending item identifier

#### Scenario: SizeOption in stop-list raises StopListError

- **WHEN** a cart references a SizeOption with `available=False` (parent MenuItem available)
- **THEN** post-GREEN `validate_stop_list` raises `StopListError`

#### Scenario: Modifier in stop-list raises StopListError

- **WHEN** a cart references a Modifier with `available=False`
- **THEN** post-GREEN `validate_stop_list` raises `StopListError`

#### Scenario: stale MenuItem price returned from validator

- **WHEN** a cart has `unit_price=20000` but the DB row now has `base_price=25000`
- **THEN** post-GREEN the returned validated items expose `25000` (server is source of truth)

---

### Requirement: RED test file for working-hours / time-slot validator

**References PDD §7.5, INV-007.**

The RED cycle SHALL ship `services/core-api/tests/test_validators_working_hours.py` with tests that pin the `validate_time_slot(requested_time, order_type, shop_settings)` contract. Time is fixed via `freezegun`. `shop_settings` is a `SimpleNamespace` with `working_hours`, `default_prep_time_minutes`, `estimated_delivery_time_minutes`.

#### Scenario: ASAP pickup during working hours

- **WHEN** `now = 10:00 UTC`, working hours 08:00–22:00, `requested_time=None`, `order_type=PICKUP`, `prep_time=15`
- **THEN** post-GREEN the return is `10:15 UTC`; in RED the function is missing

#### Scenario: ASAP delivery adds estimated delivery time

- **WHEN** `now = 10:00 UTC`, `order_type=DELIVERY`, `prep_time=15`, `estimated_delivery_time_minutes=30`
- **THEN** post-GREEN the return is `10:45 UTC`

#### Scenario: ASAP while closed, next opening ≤24h

- **WHEN** `now = 02:00 UTC`, working hours 08:00–22:00, `requested_time=None`, `order_type=PICKUP`, `prep_time=15`
- **THEN** post-GREEN the return is `08:15 UTC` (opening + prep_time)

#### Scenario: ASAP while closed >24h — reject

- **WHEN** `now = 02:00 UTC` on a day whose next opening is >24h away (e.g. configured closed days)
- **THEN** post-GREEN `validate_time_slot` raises `TimeSlotValidationError`

#### Scenario: explicit time in the past rejects

- **WHEN** `now = 10:00 UTC`, `requested_time = 09:00 UTC`
- **THEN** post-GREEN raises `TimeSlotValidationError`

#### Scenario: explicit time below prep_time rejects

- **WHEN** `now = 10:00 UTC`, `prep_time=15`, `requested_time = 10:10 UTC`
- **THEN** post-GREEN raises `TimeSlotValidationError`

#### Scenario: explicit time outside working hours rejects

- **WHEN** working hours 08:00–22:00, `requested_time = 23:00 UTC`
- **THEN** post-GREEN raises `TimeSlotValidationError`

#### Scenario: explicit time inside working hours accepts

- **WHEN** `now = 10:00 UTC`, `requested_time = 14:00 UTC`, working hours 08:00–22:00
- **THEN** post-GREEN returns `14:00 UTC` unchanged

---

### Requirement: RED test file for delivery validators

**References PDD §7.3 step 3, §7.4 step 1, INV-008, INV-009.**

The RED cycle SHALL ship `services/core-api/tests/test_validators_delivery.py` with tests for `validate_delivery_address(lat, lon, shop_settings)` and `validate_min_delivery_amount(subtotal, shop_settings)`. Pure tests — no DB.

#### Scenario: address inside radius accepts

- **WHEN** shop at `(55.7558, 37.6173)`, radius 5 km, address at `(55.7600, 37.6200)` (~0.5 km away)
- **THEN** post-GREEN `validate_delivery_address` returns `None` (no raise); in RED the function is missing

#### Scenario: address outside radius raises DeliveryRadiusError

- **WHEN** shop at `(55.7558, 37.6173)`, radius 5 km, address at `(55.9000, 37.6173)` (~16 km north)
- **THEN** post-GREEN raises `DeliveryRadiusError`

#### Scenario: Haversine uses Earth radius 6371 km

- **WHEN** the test checks `validate_delivery_address(shop_lat, shop_lon, shop_settings)` at the shop itself
- **THEN** post-GREEN no exception is raised (distance = 0); this sanity-checks the constant

#### Scenario: subtotal below min_delivery_amount raises

- **WHEN** `subtotal=40000`, `shop_settings.min_delivery_amount=50000`
- **THEN** post-GREEN raises `MinimumDeliveryAmountError`

#### Scenario: subtotal equal to min_delivery_amount accepts

- **WHEN** `subtotal=50000`, `shop_settings.min_delivery_amount=50000`
- **THEN** post-GREEN returns `None` (INV-009 boundary — strictly below rejects, equal accepts)

#### Scenario: subtotal above min_delivery_amount accepts

- **WHEN** `subtotal=200000`, `shop_settings.min_delivery_amount=50000`
- **THEN** post-GREEN returns `None`

---

### Requirement: RED test file for promocode validator

**References PDD §5.2 (Промокоды, "Примечания"), INV-011.**

The RED cycle SHALL ship `services/core-api/tests/test_validators_promocode.py` with tests that pin the `validate_promocode(code, user_id, subtotal, db_session)` contract. Tests use `migrated_db_session` and seed `Promocode` + `PromocodeUsage` rows directly.

#### Scenario: unknown code raises

- **WHEN** the test calls `validate_promocode("WRONG", user_id, 100000, session)` with no matching row
- **THEN** post-GREEN raises `PromocodeValidationError`; in RED the import fails

#### Scenario: inactive promocode raises

- **WHEN** the stored row has `is_active=False`
- **THEN** post-GREEN raises `PromocodeValidationError`

#### Scenario: valid_from in future raises

- **WHEN** now is before `valid_from`
- **THEN** post-GREEN raises `PromocodeValidationError`

#### Scenario: valid_until in past raises

- **WHEN** now is after `valid_until`
- **THEN** post-GREEN raises `PromocodeValidationError`

#### Scenario: global quota exhausted raises

- **WHEN** `current_uses >= max_uses`
- **THEN** post-GREEN raises `PromocodeValidationError`

#### Scenario: per-user quota exhausted raises

- **WHEN** `max_uses_per_user=2` and `promocode_usages` has 2 rows for (user_id, promocode_id)
- **THEN** post-GREEN raises `PromocodeValidationError`

#### Scenario: subtotal below min_order_amount raises

- **WHEN** `min_order_amount=150000` and `subtotal=100000`
- **THEN** post-GREEN raises `PromocodeValidationError`

#### Scenario: all checks pass — returns the Promocode row

- **WHEN** all validity conditions hold
- **THEN** post-GREEN returns the matching `Promocode` ORM instance (GREEN cycle may choose to return the ORM object or a DTO; the RED test asserts `.code == "<code>"`)

---

### Requirement: RED package-init smoke test

**References this design §D1 (validators live in a package).**

The RED cycle SHALL ship `services/core-api/tests/test_validators_init.py` to pin the public surface of the `core_api.services.validators` package.

#### Scenario: public validator names importable from package root

- **WHEN** the test executes `from core_api.services.validators import validate_stop_list, validate_time_slot, validate_delivery_address, validate_min_delivery_amount, validate_promocode`
- **THEN** post-GREEN the import succeeds; in RED the import raises `ImportError` (package or symbols missing)

#### Scenario: exception classes importable from validators.exceptions

- **WHEN** the test executes `from core_api.services.validators.exceptions import StopListError, PromocodeValidationError, MinimumDeliveryAmountError, DeliveryRadiusError, TimeSlotValidationError`
- **THEN** post-GREEN the import succeeds; in RED it raises `ImportError`

---

### Requirement: VERIFY — full RED test run fails or skips only

The RED cycle SHALL be verified by running the new test files against the current (pre-GREEN) codebase. Every new test MUST either FAIL (`ImportError`/`AttributeError`) or be a legitimate skip. No test SHALL pass by accident. Existing Phase-1/Phase-2/Phase-3 tests MUST remain green.

#### Scenario: pytest on new files only

- **WHEN** the developer runs `docker compose exec core-api pytest services/core-api/tests/test_pricing_chain.py services/core-api/tests/test_validators_*.py -v`
- **THEN** every selected test reports FAILED or SKIPPED; none PASSES

#### Scenario: full suite still green on untouched tests

- **WHEN** the developer runs `docker compose exec core-api pytest services/core-api/tests/ -v --ignore=services/core-api/tests/test_pricing_chain.py --ignore-glob='services/core-api/tests/test_validators_*.py'`
- **THEN** no pre-existing test regresses; the suite is green
