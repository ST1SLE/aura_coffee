## 1. GREEN — atomic increment in checkout

- [x] 1.1 [core-api] EDIT: In `services/core-api/src/core_api/services/checkout.py`, add `from sqlalchemy import or_, update` to the imports at the top (keep the existing `select` import). Also import `Promocode`: `from shared.models import ... Promocode, ...` — add it alongside the existing model imports.
- [x] 1.2 [core-api] EDIT: In `checkout.py::create_order`, locate the block:
  ```python
  # PromocodeUsage
  if promocode is not None:
      db_session.add(
          PromocodeUsage(
              promocode_id=promocode.id,
              user_id=user_id,
              order_id=order.id,
          )
      )
      promocode.current_uses = (promocode.current_uses or 0) + 1
  ```
  Replace it with a conditional UPDATE that runs BEFORE the `PromocodeUsage` insert and raises `PromocodeValidationError("Global quota exhausted")` on zero rowcount:
  ```python
  if promocode is not None:
      from core_api.services.validators.exceptions import PromocodeValidationError
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
      db_session.add(
          PromocodeUsage(
              promocode_id=promocode.id,
              user_id=user_id,
              order_id=order.id,
          )
      )
  ```
  Ordering: the UPDATE must fire BEFORE the `PromocodeUsage` INSERT so that race-loss skips the insert entirely. The outer transaction rolls back `order`, `order_items`, `payments`, and any `LoyaltyTransaction` added earlier when the exception propagates.

## 2. GREEN — atomic decrement in cancel

- [x] 2.1 [core-api] EDIT: In `services/core-api/src/core_api/services/order_cancel.py`, add `from sqlalchemy import update` to the imports (keep existing imports).
- [x] 2.2 [core-api] EDIT: In `order_cancel.py::_return_promocode`, replace:
  ```python
  promo = db.get(Promocode, order.promocode_id)
  if promo is not None and promo.current_uses > 0:
      promo.current_uses -= 1
  ```
  with:
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
  The `db.get(Promocode, ...)` fetch can be dropped — the UPDATE targets the row by id without needing a Python-side snapshot. The subsequent `db.query(PromocodeUsage).filter_by(order_id=order.id).delete(synchronize_session=False)` and `db.flush()` stay unchanged.

## 3. VERIFY — all tests green, no regressions

- [x] 3.1 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_promocode_atomic_increment.py services/core-api/tests/test_order_cancel_atomic_decrement.py -v`. Expected: all 5 tests pass (including the race loss test that was RED pre-GREEN).
- [x] 3.2 [core-api] VERIFY: Run `docker compose exec core-api pytest services/core-api/tests/test_checkout_service.py services/core-api/tests/test_order_cancel.py -v`. Expected: no regressions (same pass count as before GREEN, namely 57 passing).
- [x] 3.3 [core-api] VERIFY: Optional full run `docker compose exec core-api pytest services/core-api/tests/ -v` — confirm nothing else broke.
