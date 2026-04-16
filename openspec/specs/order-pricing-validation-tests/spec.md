# order-pricing-validation-tests Specification

## Purpose
TBD - created by archiving change order-pricing-validation-red. Update Purpose after archive.
## Requirements
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

### Requirement: GREEN implementation of pricing chain

The GREEN cycle SHALL implement five pure functions in `services/core-api/src/core_api/services/pricing.py` such that every RED test in `services/core-api/tests/test_pricing_chain.py` passes. The module SHALL remain framework-free (existing `test_pricing_module_has_no_framework_imports` MUST continue to pass).

#### Scenario: apply_promocode — None returns (0, subtotal)

- **WHEN** the caller invokes `apply_promocode(subtotal=100000, promocode=None)`
- **THEN** the return value MUST equal `(0, 100000)`

#### Scenario: apply_promocode — PERCENT applies floor(subtotal × value / 100)

- **WHEN** the caller invokes `apply_promocode(subtotal=30333, promocode=Ns(discount_type=PERCENT, discount_value=10))`
- **THEN** the return value MUST equal `(3033, 27300)`

#### Scenario: apply_promocode — FIXED_AMOUNT caps at subtotal

- **WHEN** the caller invokes `apply_promocode(subtotal=5000, promocode=Ns(discount_type=FIXED_AMOUNT, discount_value=10000))`
- **THEN** the return value MUST equal `(5000, 0)`

#### Scenario: apply_loyalty_points — requested > balance uses entire balance

- **WHEN** the caller invokes `apply_loyalty_points(after_promo=20000, requested_points=50000, user_balance=15000)`
- **THEN** the return value MUST equal `(15000, 5000)` and no exception is raised

#### Scenario: apply_loyalty_points — redeemable cap at after_promo

- **WHEN** the caller invokes `apply_loyalty_points(after_promo=10000, requested_points=50000, user_balance=50000)`
- **THEN** the return value MUST equal `(10000, 0)`

#### Scenario: compute_delivery_fee — subtotal below min raises

- **WHEN** `subtotal=40000`, `min_delivery_amount=50000`
- **THEN** `compute_delivery_fee` MUST raise `MinimumDeliveryAmountError` imported from `core_api.services.validators.exceptions`

#### Scenario: compute_delivery_fee — free over threshold

- **WHEN** `subtotal=200000`, `free_delivery_threshold=150000`
- **THEN** the return value MUST be `0`

#### Scenario: compute_delivery_fee — paid between min and threshold

- **WHEN** `subtotal=100000`, `min_delivery_amount=50000`, `free_delivery_threshold=150000`, `delivery_fee=20000`
- **THEN** the return value MUST be `20000`

#### Scenario: compute_order_total sums after_points + delivery_fee

- **WHEN** the caller invokes `compute_order_total(after_points=12345, delivery_fee=20000)`
- **THEN** the return value MUST be `32345`

#### Scenario: compute_estimated_accrual — INV-003 floor

- **WHEN** `compute_estimated_accrual(after_points=10050, loyalty_percent=5)`
- **THEN** the return value MUST be `502` (`floor(10050 × 5 / 100)`)

#### Scenario: compute_estimated_accrual — zero after 100% points

- **WHEN** `after_points=0`, `loyalty_percent=5`
- **THEN** the return value MUST be `0`

#### Scenario: pricing module remains framework-free

- **WHEN** `test_pricing_module_has_no_framework_imports` runs after GREEN
- **THEN** `pricing.py` MUST NOT import `sqlalchemy`, `redis`, `fastapi`, `pydantic`, `core_api.models`, or `shared.models`

---

### Requirement: GREEN implementation of validators package

The GREEN cycle SHALL create `services/core-api/src/core_api/services/validators/` as a Python package containing `__init__.py`, `exceptions.py`, `stop_list.py`, `working_hours.py`, `delivery.py`, and `promocode.py`. The package `__init__.py` MUST re-export `validate_stop_list`, `validate_time_slot`, `validate_delivery_address`, `validate_min_delivery_amount`, and `validate_promocode`.

#### Scenario: package exports five public validators

- **WHEN** a caller runs `from core_api.services.validators import validate_stop_list, validate_time_slot, validate_delivery_address, validate_min_delivery_amount, validate_promocode`
- **THEN** every symbol MUST import successfully and each MUST be callable

#### Scenario: exceptions module exports five domain errors + ValidationError base

- **WHEN** a caller runs `from core_api.services.validators.exceptions import ValidationError, StopListError, PromocodeValidationError, MinimumDeliveryAmountError, DeliveryRadiusError, TimeSlotValidationError`
- **THEN** every symbol MUST import successfully and each domain error MUST be a subclass of `ValidationError`, which itself MUST be a subclass of `Exception`

---

### Requirement: GREEN implementation of validate_stop_list

`validate_stop_list(cart_items, db_session)` SHALL re-read MenuItem, SizeOption, and Modifier rows from the database and MUST raise `StopListError` (carrying `item_id`) on any unavailable reference. On success the validator MUST return a list of items where `unit_price` reflects the current DB value (INV-006).

#### Scenario: all available — returns validated items with fresh prices

- **WHEN** a cart references a MenuItem with `available=True` and the caller invokes `validate_stop_list(cart, session)`
- **THEN** the return value MUST be a list of dicts whose `unit_price` is taken from the DB row (not the client-supplied value)

#### Scenario: unavailable MenuItem raises StopListError with item_id

- **WHEN** a cart references a MenuItem with `available=False`
- **THEN** `validate_stop_list` MUST raise `StopListError` whose `.item_id` attribute equals the unavailable MenuItem's id

#### Scenario: unavailable SizeOption raises

- **WHEN** a cart references a SizeOption with `available=False`
- **THEN** `validate_stop_list` MUST raise `StopListError`

#### Scenario: unavailable Modifier raises

- **WHEN** a cart references a Modifier with `available=False`
- **THEN** `validate_stop_list` MUST raise `StopListError`

---

### Requirement: GREEN implementation of validate_time_slot

`validate_time_slot(requested_time, order_type, shop_settings, now=None)` SHALL accept a clock override via `now=`. For ASAP (`requested_time is None`) the validator MUST add `default_prep_time_minutes` (+ `estimated_delivery_time_minutes` when `OrderType.DELIVERY`). Outside working hours, the validator MUST search the next opening within 24h or raise `TimeSlotValidationError`. Explicit times MUST be in the future, MUST be at least `prep_time` ahead of `now`, and MUST fall within working hours.

#### Scenario: ASAP pickup during working hours

- **WHEN** `now=10:00 UTC`, `requested_time=None`, `order_type=PICKUP`, `prep_time=15`
- **THEN** the return value MUST be `10:15 UTC`

#### Scenario: ASAP delivery adds estimated delivery time

- **WHEN** `now=10:00 UTC`, `order_type=DELIVERY`, `prep_time=15`, `estimated_delivery_time_minutes=30`
- **THEN** the return value MUST be `10:45 UTC`

#### Scenario: ASAP while closed, next opening ≤24h

- **WHEN** `now=02:00 UTC`, working_hours 08:00–22:00, `order_type=PICKUP`
- **THEN** the return value MUST be `08:15 UTC`

#### Scenario: ASAP while closed >24h raises

- **WHEN** all working_hours are empty (closed every day)
- **THEN** `validate_time_slot` MUST raise `TimeSlotValidationError`

#### Scenario: explicit past raises

- **WHEN** `requested_time < now`
- **THEN** `validate_time_slot` MUST raise `TimeSlotValidationError`

#### Scenario: explicit within prep_time raises

- **WHEN** `requested_time - now < prep_time`
- **THEN** `validate_time_slot` MUST raise `TimeSlotValidationError`

#### Scenario: explicit outside working hours raises

- **WHEN** `requested_time=23:00`, working_hours close at 22:00
- **THEN** `validate_time_slot` MUST raise `TimeSlotValidationError`

#### Scenario: explicit within hours accepts

- **WHEN** `requested_time=14:00`, working_hours 08:00–22:00, `now=10:00`
- **THEN** the return value MUST equal `requested_time` unchanged

---

### Requirement: GREEN implementation of delivery validators

`validate_delivery_address(lat, lon, shop_settings)` SHALL apply the Haversine formula with Earth radius `6371.0` km and MUST raise `DeliveryRadiusError` when the computed distance exceeds `delivery_radius_km`. `validate_min_delivery_amount(subtotal, shop_settings)` MUST raise `MinimumDeliveryAmountError` when `subtotal < min_delivery_amount` (strict); equality accepts.

#### Scenario: inside radius accepts

- **WHEN** shop at `(55.7558, 37.6173)`, radius 5 km, address `(55.7600, 37.6200)`
- **THEN** `validate_delivery_address` MUST return `None`

#### Scenario: outside radius raises

- **WHEN** shop at `(55.7558, 37.6173)`, radius 5 km, address `(55.9000, 37.6173)`
- **THEN** `validate_delivery_address` MUST raise `DeliveryRadiusError`

#### Scenario: distance zero at shop coords

- **WHEN** the address equals shop coords
- **THEN** `validate_delivery_address` MUST return `None`

#### Scenario: subtotal below min raises

- **WHEN** `subtotal=40000`, `min_delivery_amount=50000`
- **THEN** `validate_min_delivery_amount` MUST raise `MinimumDeliveryAmountError`

#### Scenario: subtotal equal to min accepts

- **WHEN** `subtotal=50000`, `min_delivery_amount=50000`
- **THEN** `validate_min_delivery_amount` MUST return `None`

---

### Requirement: GREEN implementation of validate_promocode

`validate_promocode(code, user_id, subtotal, db_session)` SHALL run a 7-check chain — code existence, `is_active`, `valid_from`, `valid_until`, global quota, per-user quota (via COUNT of `PromocodeUsage` rows for `(promocode_id, user_id)`), and `min_order_amount` — and MUST raise `PromocodeValidationError` on any failure. On success the validator MUST return the matching `Promocode` ORM instance.

#### Scenario: unknown code raises

- **WHEN** no row matches `code`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: inactive raises

- **WHEN** the row has `is_active=False`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: valid_from future raises

- **WHEN** `now < valid_from`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: valid_until past raises

- **WHEN** `now > valid_until`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: global quota exhausted raises

- **WHEN** `current_uses >= max_uses`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: per-user quota exhausted raises

- **WHEN** `max_uses_per_user=2` and two `PromocodeUsage` rows exist for `(promocode_id, user_id)`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: subtotal below min_order_amount raises

- **WHEN** `subtotal=100000` and `min_order_amount=150000`
- **THEN** `validate_promocode` MUST raise `PromocodeValidationError`

#### Scenario: happy path returns the Promocode ORM row

- **WHEN** all checks pass
- **THEN** the return value MUST be the `Promocode` row whose `.code` equals the requested code

---

### Requirement: GREEN VERIFY — full RED test run passes

Every RED test introduced by `order-pricing-validation-red` MUST pass after the GREEN implementation is merged. Pre-existing Phase-1/Phase-2/Phase-3 tests MUST NOT regress.

#### Scenario: RED tests flip to PASS

- **WHEN** the developer runs `docker compose exec core-api pytest services/core-api/tests/test_pricing_chain.py services/core-api/tests/test_validators_stop_list.py services/core-api/tests/test_validators_working_hours.py services/core-api/tests/test_validators_delivery.py services/core-api/tests/test_validators_promocode.py services/core-api/tests/test_validators_init.py -v`
- **THEN** every test MUST report PASSED

#### Scenario: full suite unaffected on untouched tests

- **WHEN** the developer runs the rest of the suite
- **THEN** no pre-existing test SHALL regress

