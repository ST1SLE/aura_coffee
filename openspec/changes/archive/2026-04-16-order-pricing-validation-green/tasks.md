## 1. Exceptions module (foundation)

- [x] 1.1 [core-api] Create `services/core-api/src/core_api/services/validators/__init__.py` as empty package marker (will be filled in task group 7).
- [x] 1.2 [core-api] Create `services/core-api/src/core_api/services/validators/exceptions.py` with `ValidationError(Exception)` base and five subclasses: `StopListError` (carries `item_id: int | None` kwarg), `PromocodeValidationError`, `MinimumDeliveryAmountError`, `DeliveryRadiusError`, `TimeSlotValidationError`. No framework imports.
- [x] 1.3 [core-api] VERIFY: run `pytest services/core-api/tests/test_validators_init.py::test_validators_exceptions_module_exports_error_classes services/core-api/tests/test_validators_init.py::test_validators_exceptions_share_base_class` — both MUST pass.

## 2. Pricing chain extensions

- [x] 2.1 [core-api] Extend `services/core-api/src/core_api/services/pricing.py`: add `apply_promocode(subtotal: int, promocode: Any | None) -> tuple[int, int]` branching on `PromocodeDiscountType.PERCENT` (floor `(subtotal * value) // 100`) vs `FIXED_AMOUNT` (use value directly); discount capped at `subtotal`; return `(discount, subtotal - discount)`.
- [x] 2.2 [core-api] Add `apply_loyalty_points(after_promo: int, requested_points: int, user_balance: int) -> tuple[int, int]`: `used = min(requested_points, user_balance, after_promo)`; return `(used, after_promo - used)`. No exception for over-request.
- [x] 2.3 [core-api] Add `compute_delivery_fee(subtotal: int, shop_settings: Any) -> int`: raise `MinimumDeliveryAmountError` (imported from `core_api.services.validators.exceptions`) when `subtotal < shop_settings.min_delivery_amount`; return `0` when `subtotal >= free_delivery_threshold`; else return `int(shop_settings.delivery_fee)`.
- [x] 2.4 [core-api] Add `compute_order_total(after_points: int, delivery_fee: int) -> int`: return `after_points + delivery_fee`.
- [x] 2.5 [core-api] Add `compute_estimated_accrual(after_points: int, loyalty_percent: int) -> int`: return `(after_points * loyalty_percent) // 100` (INV-003).
- [x] 2.6 [core-api] VERIFY purity: `pricing.py` imports only `shared.enums.PromocodeDiscountType` and `core_api.services.validators.exceptions.MinimumDeliveryAmountError` on top of stdlib. No `sqlalchemy`, `fastapi`, `pydantic`.
- [x] 2.7 [core-api] VERIFY: `pytest services/core-api/tests/test_pricing_chain.py -v` reports 19 passing.
- [x] 2.8 [core-api] VERIFY: `pytest services/core-api/tests/test_pricing.py::test_pricing_module_has_no_framework_imports` still passes.

## 3. Stop-list validator

- [x] 3.1 [core-api] Create `services/core-api/src/core_api/services/validators/stop_list.py` with `validate_stop_list(cart_items, db_session)` using `shared.models.menu_item.MenuItem`, `shared.models.size_option.SizeOption`, `shared.models.modifier.Modifier`. Collect ids, issue up to 3 `SELECT ... WHERE id IN (...)` queries, iterate cart items, raise `StopListError(item_id=<menu_item_id>)` on any unavailable reference, compute fresh `unit_price = size.price if size else menu.base_price` + sum(`mod.price`), return list of `{**original_item, "unit_price": fresh_price}`.
- [x] 3.2 [core-api] VERIFY: `pytest services/core-api/tests/test_validators_stop_list.py -v` reports 6 passing.

## 4. Working-hours validator

- [x] 4.1 [core-api] Create `services/core-api/src/core_api/services/validators/working_hours.py` with `validate_time_slot(requested_time, order_type, shop_settings, now=None)`. Default `now = datetime.now(UTC)`. Compute `prep = timedelta(minutes=default_prep_time_minutes)` and `delivery_extra = timedelta(minutes=estimated_delivery_time_minutes) if order_type == DELIVERY else timedelta(0)`.
- [x] 4.2 [core-api] For ASAP branch: `estimated = now + prep + delivery_extra`; if `_is_within_hours(estimated, working_hours)` return it; else call `_next_opening_within_24h(now, working_hours)` and return `opening + prep + delivery_extra` or raise `TimeSlotValidationError` if no opening within 24h.
- [x] 4.3 [core-api] For explicit-time branch: raise if `requested_time <= now`, if `requested_time - now < prep`, or if `not _is_within_hours(requested_time, working_hours)`; else return `requested_time`.
- [x] 4.4 [core-api] Implement `_is_within_hours(dt, working_hours)`: lookup `working_hours.get(dt.strftime("%a").lower())`; parse `"HH:MM"` open/close; compare `dt.time()` range.
- [x] 4.5 [core-api] Implement `_next_opening_within_24h(now, working_hours)`: walk up to 24 hourly increments across days, return first `datetime` >= now where the time == opening time; None if unreachable within 24h. Simple loop acceptable (perf irrelevant).
- [x] 4.6 [core-api] VERIFY: `pytest services/core-api/tests/test_validators_working_hours.py -v` reports 8 passing.

## 5. Delivery validators

- [x] 5.1 [core-api] Create `services/core-api/src/core_api/services/validators/delivery.py` with Haversine `validate_delivery_address(lat, lon, shop_settings) -> None` using Earth radius `6371.0` km; raise `DeliveryRadiusError` when `distance_km > shop_settings.delivery_radius_km`.
- [x] 5.2 [core-api] Add `validate_min_delivery_amount(subtotal: int, shop_settings) -> None`: raise `MinimumDeliveryAmountError` when `subtotal < shop_settings.min_delivery_amount` (strict); equal accepts.
- [x] 5.3 [core-api] VERIFY: `pytest services/core-api/tests/test_validators_delivery.py -v` reports 6 passing.

## 6. Promocode validator

- [x] 6.1 [core-api] Create `services/core-api/src/core_api/services/validators/promocode.py` with `validate_promocode(code, user_id, subtotal, db_session) -> Promocode`. Use `shared.models.promocode.Promocode` and `shared.models.promocode_usage.PromocodeUsage`.
- [x] 6.2 [core-api] Implement the 7-check chain in order: unknown code → `is_active=False` → `now < valid_from` → `now > valid_until` → `current_uses >= max_uses` (if `max_uses` set) → per-user COUNT `>= max_uses_per_user` (if set) → `subtotal < min_order_amount`. Raise `PromocodeValidationError` on any violation; return the `Promocode` row on success. Use `datetime.now(UTC)` for time comparisons.
- [x] 6.3 [core-api] VERIFY: `pytest services/core-api/tests/test_validators_promocode.py -v` reports 8 passing.

## 7. Package __init__ re-exports

- [x] 7.1 [core-api] Populate `services/core-api/src/core_api/services/validators/__init__.py` with re-exports: `from .stop_list import validate_stop_list`, `from .working_hours import validate_time_slot`, `from .delivery import validate_delivery_address, validate_min_delivery_amount`, `from .promocode import validate_promocode`. Define `__all__` with these five names.
- [x] 7.2 [core-api] VERIFY: `pytest services/core-api/tests/test_validators_init.py -v` reports 3 passing.

## 8. Full VERIFY

- [x] 8.1 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_pricing_chain.py services/core-api/tests/test_validators_stop_list.py services/core-api/tests/test_validators_working_hours.py services/core-api/tests/test_validators_delivery.py services/core-api/tests/test_validators_promocode.py services/core-api/tests/test_validators_init.py -v` — all 50 tests MUST pass.
- [x] 8.2 [core-api] VERIFY: run `docker compose exec core-api pytest services/core-api/tests/test_pricing.py -v` — pre-existing pricing tests including the framework-import-check MUST pass.
