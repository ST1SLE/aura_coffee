## Why

RED (`promocode-race-fix-red`) locked the atomic-increment contract and left `test_race_loss_raises_validation_error_and_does_not_overshoot_max_uses` failing. GREEN replaces the ORM attribute mutation in `core_api.services.checkout.create_order` and `core_api.services.order_cancel._return_promocode` with the conditional UPDATEs specified by PDD §6.6, turning the DB into the single source of truth for quota enforcement.

MVP phase: **Phase 3 — Order Pricing & Cancel** (PDD §7.1).

## What Changes

- `core_api.services.checkout.create_order`: replace `promocode.current_uses = (promocode.current_uses or 0) + 1` with a conditional UPDATE:
  ```python
  from sqlalchemy import or_, update
  result = db_session.execute(
      update(Promocode)
      .where(
          Promocode.id == promocode.id,
          or_(
              Promocode.max_uses.is_(None),
              Promocode.current_uses < Promocode.max_uses,
          ),
      )
      .values(current_uses=Promocode.current_uses + 1)
  )
  if result.rowcount == 0:
      raise PromocodeValidationError("Global quota exhausted")
  ```
  The PromocodeUsage row SHALL be added only on `rowcount == 1`. On zero rowcount the exception propagates; the outer transaction rolls back as a whole.
- `core_api.services.order_cancel._return_promocode`: replace `promo.current_uses -= 1` with:
  ```python
  db.execute(
      update(Promocode)
      .where(
          Promocode.id == order.promocode_id,
          Promocode.current_uses > 0,
      )
      .values(current_uses=Promocode.current_uses - 1)
  )
  ```
  The `PromocodeUsage` delete and the rest of the cancel chain remain unchanged.
- `core_api.services.validators.promocode` is NOT modified — it keeps serving fast 422 rejection for obviously invalid codes. The atomic UPDATE is the load-bearing guard.

## Capabilities

### Modified Capabilities
- `order-checkout`: conditional UPDATE for promocode increment replaces ORM mutation. External 422 contract preserved.
- `order-cancel`: conditional UPDATE with zero-floor replaces ORM decrement. Double-cancel behavior unchanged.

## Non-Goals

- Touching `core_api.services.validators.promocode`.
- `SELECT ... FOR UPDATE`, advisory locks, or isolation-level changes.
- Schema changes.
- Per-user quota hardening.
- Frontend work.

## Impact

- **Code**: `services/core-api/src/core_api/services/checkout.py`, `services/core-api/src/core_api/services/order_cancel.py`.
- **Tests**: the five tests in `test_promocode_atomic_increment.py` and `test_order_cancel_atomic_decrement.py` all pass post-GREEN. Pre-existing `test_checkout_service.py` and `test_order_cancel.py` continue to pass (contract unchanged).
- **APIs**: no change to external HTTP 422 contract.
- **Dependencies**: only `sqlalchemy.update` and `sqlalchemy.or_` — already in use.
- **Inviolable rules touched**: INV-004, INV-011 (now actually enforced at the DB).
