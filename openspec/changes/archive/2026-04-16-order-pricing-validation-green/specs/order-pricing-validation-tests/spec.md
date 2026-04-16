## ADDED Requirements

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
