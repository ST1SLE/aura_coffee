## ADDED Requirements

_References: PDD §6.6 (Атомарный инкремент `current_uses`), §7.2 step 2 (Promocode application), INV-004 (atomic transaction), INV-011 (quota honoured)._

### Requirement: Promocode usage counter SHALL be incremented atomically

`core_api.services.checkout.create_order` SHALL bump `promocodes.current_uses` through a single conditional UPDATE that includes the remaining-quota predicate inside its `WHERE` clause. The validator at `core_api.services.validators.promocode` MAY read-check the quota for UX, but the load-bearing guarantee lives in the UPDATE — not the validator.

The UPDATE SHALL match when `id = :promo_id AND (max_uses IS NULL OR current_uses < max_uses)`. Its `SET` clause SHALL be `current_uses = current_uses + 1` (self-reference, so the DB — not the Python snapshot — produces the new value). On `rowcount == 0`, the service SHALL raise `core_api.services.validators.exceptions.PromocodeValidationError` with the same human-readable message the validator emits for global-quota exhaustion (`"Global quota exhausted"`). The checkout transaction SHALL be rolled back as a whole on this error, exactly as if the pre-transaction validator had rejected the code. The external HTTP contract SHALL remain HTTP 422 with the same message — the client MUST NOT be able to distinguish "code already exhausted" from "lost the race".

When a promocode with `max_uses IS NULL` is applied, the conditional UPDATE SHALL still match and increment `current_uses`.

#### Scenario: Atomic race — validator's view is stale by the time UPDATE fires
- **GIVEN** a promocode `P` with `max_uses=1`, `current_uses=0`
- **AND** the checkout validator has already been invoked for user A's cart (observing `current_uses=0`)
- **WHEN** a concurrent transaction advances `current_uses` to `1` (simulated by a raw `UPDATE promocodes SET current_uses=1 WHERE id=P.id` between validator call and the pricing/write phase of `create_order`)
- **AND** `create_order` proceeds to the increment step
- **THEN** the conditional UPDATE SHALL match zero rows
- **AND** `create_order` SHALL raise `PromocodeValidationError("Global quota exhausted")`
- **AND** the row SHALL end with `current_uses=1` (never `2`)
- **AND** no `orders`, `order_items`, `payments`, or `promocode_usages` row SHALL be committed for the losing transaction

#### Scenario: Unlimited promocode (`max_uses IS NULL`) still increments
- **GIVEN** a promocode `P` with `max_uses=None`, `current_uses=42`
- **WHEN** `create_order` applies `P` on a valid cart
- **THEN** the conditional UPDATE SHALL match exactly one row
- **AND** `P.current_uses` SHALL be `43` after commit
- **AND** the order SHALL commit normally

#### Scenario: Under quota — single-row match on the remaining-quota predicate
- **GIVEN** a promocode `P` with `max_uses=5`, `current_uses=2`
- **WHEN** `create_order` applies `P` on a valid cart
- **THEN** the conditional UPDATE SHALL match exactly one row
- **AND** `P.current_uses` SHALL be `3` after commit
