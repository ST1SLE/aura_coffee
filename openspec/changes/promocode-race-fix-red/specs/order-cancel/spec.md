## MODIFIED Requirements

_References: PDD §6.6 (Атомарный инкремент `current_uses`), §7.6 step 2 (Возврат промокода), INV-004 (atomicity), INV-011 (quota honoured)._

### Requirement: Promocode usage counter SHALL be decremented atomically with a zero floor

`core_api.services.order_cancel._return_promocode` SHALL decrement `promocodes.current_uses` through a single conditional UPDATE whose `WHERE` clause includes the floor predicate `current_uses > 0`. The `SET` clause SHALL be `current_uses = current_uses - 1` (self-reference). Concurrent double-cancel attempts SHALL NOT drive `current_uses` below zero: the second attempt's UPDATE SHALL match zero rows and SHALL be a no-op on the counter.

#### Scenario: Double-cancel race — second decrement is a floored no-op
- **GIVEN** a promocode `P` with `current_uses=1` and an order `O` that redeemed `P`
- **AND** `_return_promocode(O, db)` has already been invoked once (current_uses decremented to `0`, PromocodeUsage row removed)
- **WHEN** `_return_promocode(O, db)` is invoked a second time (simulating a stale admin-path retry)
- **THEN** the conditional UPDATE SHALL match zero rows
- **AND** `P.current_uses` SHALL remain `0` — NEVER `-1`

#### Scenario: Normal cancel path decrements once
- **GIVEN** a promocode `P` with `current_uses=3` and an order `O` that redeemed `P`
- **WHEN** `_return_promocode(O, db)` is invoked
- **THEN** the conditional UPDATE SHALL match exactly one row
- **AND** `P.current_uses` SHALL be `2` after commit
- **AND** the `PromocodeUsage` row for `O` SHALL be deleted
