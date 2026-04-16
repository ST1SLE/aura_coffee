## Context

**Affected modules:** [core-api].

The RED cycle ships 50 failing tests that pin contracts for:
1. Five new pure functions in `core_api.services.pricing` (extends existing `_compute_unit_price`, `compute_line_total`, `compute_subtotal`).
2. A new `core_api.services.validators` package with four validator modules, an `__init__.py` re-exporting the public surface, and an `exceptions.py` with a shared `ValidationError` base + five domain-specific subclasses.

This GREEN cycle SHALL implement the functions/modules in a way that makes every RED test pass on the first run, without touching routers, migrations, or seeds.

## Goals / Non-Goals

**Goals:**
- Implement five pure functions in `pricing.py` with integer (kopeck) arithmetic and Python `math.floor` semantics via `//`.
- Build validators package with four modules + exceptions + `__init__.py`.
- Preserve `test_pricing_module_has_no_framework_imports` — pricing.py MUST NOT import sqlalchemy, fastapi, or pydantic.
- Validators MAY import sqlalchemy (stop_list and promocode need DB access per RED contract).

**Non-Goals:**
- No router wiring; no HTTPException conversion.
- No checkout orchestrator function that composes pricing + validators.
- No migrations, seeds, or schema changes.
- No performance optimisation (Haversine may use `math.radians`/`math.sin` directly; promocode validator may issue multiple SQL queries).
- No i18n of exception messages (error.args[0] is English; router layer will localise later).

## Decisions

### D1 — Pricing functions MUST remain framework-free, imports stay within stdlib and `shared.enums`

`pricing.py` SHALL import only stdlib (`math` is **not** required — integer `//` suffices) and `shared.enums.PromocodeDiscountType`. The existing AST-based test `test_pricing_module_has_no_framework_imports` is authoritative and SHALL NOT be relaxed. No typing import of SQLAlchemy models — use `Any` or `SimpleNamespace`-compatible `Protocol` (prefer `Any` for simplicity since PEP 561 isn't enforced here).

**Rationale:** Pure pricing is cheap to unit-test, portable between core-api and future admin-panel "dry run" previews, and matches the Phase-2 established convention.

### D2 — `apply_promocode` branches on `promocode.discount_type` with integer floor division

```python
def apply_promocode(subtotal: int, promocode: Any | None) -> tuple[int, int]:
    if promocode is None:
        return 0, subtotal
    if promocode.discount_type == PromocodeDiscountType.PERCENT:
        discount = (subtotal * int(promocode.discount_value)) // 100
    else:  # FIXED_AMOUNT
        discount = int(promocode.discount_value)
    discount = min(discount, subtotal)  # cap
    return discount, subtotal - discount
```

**Rationale:** PDD §7.2 step 2; INV-011 (floor); RED tests pin `(3033, 27300)` for `30333 × 10%`.

### D3 — `apply_loyalty_points` caps at `min(requested, balance, after_promo)`, NO exception on over-request

```python
def apply_loyalty_points(after_promo: int, requested_points: int, user_balance: int) -> tuple[int, int]:
    used = min(requested_points, user_balance, after_promo)
    return used, after_promo - used
```

**Rationale:** RED test `test_apply_loyalty_points_request_exceeds_balance_uses_balance` explicitly asserts no exception — the function is a pure math primitive; the checkout orchestrator (future change) may optionally surface a 400 to the user if `requested_points > balance`, but the pricing primitive tolerates it.

### D4 — `compute_delivery_fee` raises `MinimumDeliveryAmountError` from the validators package

```python
from core_api.services.validators.exceptions import MinimumDeliveryAmountError

def compute_delivery_fee(subtotal: int, shop_settings: Any) -> int:
    if subtotal < shop_settings.min_delivery_amount:
        raise MinimumDeliveryAmountError(...)
    if subtotal >= shop_settings.free_delivery_threshold:
        return 0
    return int(shop_settings.delivery_fee)
```

**Rationale:** Cross-module import (`pricing -> validators.exceptions`) is acceptable because `exceptions.py` is itself framework-free (pure Python class definitions). The RED test imports the exception from `validators.exceptions`, so the same symbol MUST be raised. Threshold comparison uses `>=` (equal to threshold → free).

### D5 — `compute_estimated_accrual` uses `after_points` as the base (INV-003)

```python
def compute_estimated_accrual(after_points: int, loyalty_percent: int) -> int:
    return (after_points * loyalty_percent) // 100
```

**Rationale:** INV-003 is explicit — accrual excludes delivery_fee AND the points-paid portion. `after_points` is already "subtotal − promo_discount − points_used", so feeding it directly matches the invariant.

### D6 — Exceptions module: single `ValidationError` base, five concrete subclasses

```python
class ValidationError(Exception):
    """Base for all domain-level order/pricing validation errors."""


class StopListError(ValidationError):
    def __init__(self, message: str, *, item_id: int | None = None) -> None:
        super().__init__(message)
        self.item_id = item_id


class PromocodeValidationError(ValidationError):
    pass


class MinimumDeliveryAmountError(ValidationError):
    pass


class DeliveryRadiusError(ValidationError):
    pass


class TimeSlotValidationError(ValidationError):
    pass
```

**Rationale:** RED tests check `issubclass(X, Exception)` AND `issubclass(X, ValidationError)`. `StopListError` carries `item_id` because `test_validate_stop_list_error_carries_offending_item_id` asserts `err.item_id == item.id`. Other subclasses are no-body for MVP (message suffices — router layer maps to HTTP 400 with localised text in a later change).

### D7 — `validate_stop_list` uses a single-trip-per-kind lookup, returns list of dicts

```python
def validate_stop_list(cart_items: list[dict], db_session: Session) -> list[dict]:
    menu_ids = {it["menu_item_id"] for it in cart_items}
    size_ids = {it["size_option_id"] for it in cart_items if it.get("size_option_id")}
    mod_ids = {m for it in cart_items for m in it.get("modifier_ids", [])}

    menus = {m.id: m for m in db_session.query(MenuItem).filter(MenuItem.id.in_(menu_ids)).all()}
    sizes = {s.id: s for s in db_session.query(SizeOption).filter(SizeOption.id.in_(size_ids)).all()}
    mods = {m.id: m for m in db_session.query(Modifier).filter(Modifier.id.in_(mod_ids)).all()}

    validated = []
    for it in cart_items:
        menu = menus.get(it["menu_item_id"])
        if menu is None or not menu.available:
            raise StopListError(f"MenuItem {it['menu_item_id']} unavailable", item_id=it["menu_item_id"])
        if it.get("size_option_id"):
            size = sizes.get(it["size_option_id"])
            if size is None or not size.available:
                raise StopListError(f"SizeOption {it['size_option_id']} unavailable", item_id=it["menu_item_id"])
            fresh_price = int(size.price)
        else:
            fresh_price = int(menu.base_price)
        for mid in it.get("modifier_ids", []):
            mod = mods.get(mid)
            if mod is None or not mod.available:
                raise StopListError(f"Modifier {mid} unavailable", item_id=it["menu_item_id"])
            fresh_price += int(mod.price)
        validated.append({**it, "unit_price": fresh_price})
    return validated
```

**Rationale:** Three queries max (menus, sizes, mods); freshest price wins (INV-006). Size price replaces base price if set; modifiers are additive. Returned shape: dict with `unit_price` overwritten.

### D8 — `validate_time_slot` uses explicit `now=None` parameter (no `freezegun`)

```python
def validate_time_slot(
    requested_time: datetime | None,
    order_type: OrderType,
    shop_settings: Any,
    now: datetime | None = None,
) -> datetime:
    if now is None:
        now = datetime.now(UTC)
    prep = timedelta(minutes=shop_settings.default_prep_time_minutes)
    delivery_extra = (
        timedelta(minutes=shop_settings.estimated_delivery_time_minutes)
        if order_type == OrderType.DELIVERY else timedelta(0)
    )
    full_lead = prep + delivery_extra

    if requested_time is None:  # ASAP
        estimated = now + full_lead
        if _is_within_hours(estimated, shop_settings.working_hours):
            return estimated
        # search next opening ≤24h
        opening = _next_opening_within_24h(now, shop_settings.working_hours)
        if opening is None:
            raise TimeSlotValidationError("No opening within 24h")
        return opening + full_lead

    if requested_time <= now:
        raise TimeSlotValidationError("requested_time in the past")
    if requested_time - now < prep:
        raise TimeSlotValidationError("requested_time below prep_time")
    if not _is_within_hours(requested_time, shop_settings.working_hours):
        raise TimeSlotValidationError("requested_time outside working hours")
    return requested_time
```

**Rationale:** `freezegun` not in dev deps; clock injection via kwarg is standard. `working_hours` keyed by lowercase 3-letter weekday (`"mon"`, `"tue"`, ...); helper walks forward up to 24h in 1-minute increments (simple; perf is irrelevant for single-site MVP). UTC-only for GREEN; timezone-aware refinement is a later change.

### D9 — `validate_delivery_address` uses Haversine with Earth radius 6371 km

```python
import math

_EARTH_RADIUS_KM = 6371.0

def validate_delivery_address(lat: float, lon: float, shop_settings: Any) -> None:
    shop_lat = float(shop_settings.shop_lat)
    shop_lon = float(shop_settings.shop_lon)
    phi1, phi2 = math.radians(shop_lat), math.radians(lat)
    dphi = math.radians(lat - shop_lat)
    dlambda = math.radians(lon - shop_lon)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance_km = _EARTH_RADIUS_KM * c
    if distance_km > float(shop_settings.delivery_radius_km):
        raise DeliveryRadiusError(f"distance {distance_km:.2f} km > radius {shop_settings.delivery_radius_km} km")
```

**Rationale:** PDD §7.3 step 3 fixes the constant. Returns `None` on success (contract from RED). Uses `>` (strictly greater) so at-exactly-radius accepts.

### D10 — `validate_promocode` runs 7-check chain, returns Promocode ORM row

```python
def validate_promocode(code: str, user_id: uuid.UUID, subtotal: int, db_session: Session) -> Promocode:
    promo = db_session.query(Promocode).filter(Promocode.code == code).first()
    if promo is None:
        raise PromocodeValidationError("Unknown code")
    if not promo.is_active:
        raise PromocodeValidationError("Inactive")
    now = datetime.now(UTC)
    if promo.valid_from and now < promo.valid_from:
        raise PromocodeValidationError("Not yet valid")
    if promo.valid_until and now > promo.valid_until:
        raise PromocodeValidationError("Expired")
    if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
        raise PromocodeValidationError("Global quota exhausted")
    if promo.max_uses_per_user is not None:
        count = db_session.query(PromocodeUsage).filter(
            PromocodeUsage.promocode_id == promo.id,
            PromocodeUsage.user_id == user_id,
        ).count()
        if count >= promo.max_uses_per_user:
            raise PromocodeValidationError("Per-user quota exhausted")
    if subtotal < int(promo.min_order_amount or 0):
        raise PromocodeValidationError("Below minimum order amount")
    return promo
```

**Rationale:** Atomicity (INV-004) is a checkout-router concern; here we only validate. Timezone-aware comparisons use `datetime.now(UTC)` — the Promocode model stores `DateTime(timezone=True)` so comparison is direct.

## Risks / Trade-offs

- **[Risk] Time-zone drift in working-hours validator** → Mitigation: lock GREEN to UTC (PDD §7.5 does not specify store-local); add a follow-up change to introduce `ShopSettings.timezone` and convert.
- **[Risk] Haversine float comparison edge cases near the radius boundary** → Mitigation: use strict `>` so equal-distance accepts; add follow-up integration tests if customers report false rejections.
- **[Risk] `validate_stop_list` issues up to 3 queries per call** → Mitigation: acceptable for single-coffee-shop cart size (< 20 items); benchmark later if needed.
- **[Risk] `ValidationError` base class name may collide with Pydantic's `ValidationError`** → Mitigation: the validators package is imported under `core_api.services.validators.exceptions`, never re-exported at top-level; router layer catches the fully-qualified symbol.

## Migration Plan

No DB migration. Forward-only code change; rollback = revert commit (no data side effects).

## Open Questions

None for GREEN; timezone-aware working-hours is explicitly deferred (Non-Goal in proposal).

## Atomicity Analysis

N/A — this change adds **read-only** validators and **pure** pricing functions; no financial writes. Financial atomicity (INV-004) is the responsibility of the future checkout-orchestration change that composes these primitives.

## 152-FZ Compliance

N/A — no PII introduced. `validate_promocode` reads `user_id` (UUID, not PII) and `PromocodeUsage` (join-only); no `phone_hash` or profile access.

## State-machine Impact

N/A — no state transitions. Validators run before `Order` creation; order-status transitions are owned by router/service code that is out of scope here.
