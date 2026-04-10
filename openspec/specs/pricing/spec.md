## Requirements

_References: PDD §7.2 step 1 (Order Pricing Chain — Subtotal), INV-014 (immutable order items), PDD §3 (Cart Item pricing formula)._

### Requirement: compute_line_total implements PDD §7.2 step 1 exactly

The system SHALL expose a pure function `compute_line_total(base_price: int, size_price: int | None, modifier_prices: Iterable[int], quantity: int) -> int` at `core_api.services.pricing`. It SHALL compute `unit_price = (size_price if size_price is not None else base_price) + sum(modifier_prices)` and return `unit_price * quantity`. All prices are integer kopecks. The function MUST NOT import `sqlalchemy`, `redis`, `fastapi`, or `core_api.models` — it depends only on `typing`, `collections.abc`, and the standard library.

#### Scenario: Base price only with no size and no modifiers
- **WHEN** calling `compute_line_total(base_price=15000, size_price=None, modifier_prices=[], quantity=1)`
- **THEN** the result SHALL equal `15000`

#### Scenario: Size price overrides base price
- **WHEN** calling `compute_line_total(base_price=15000, size_price=20000, modifier_prices=[], quantity=1)`
- **THEN** the result SHALL equal `20000` (base_price is ignored when a size is selected)

#### Scenario: Modifiers sum into unit_price
- **WHEN** calling `compute_line_total(base_price=15000, size_price=None, modifier_prices=[3000, 5000], quantity=1)`
- **THEN** the result SHALL equal `23000`

#### Scenario: Quantity multiplies the unit price
- **WHEN** calling `compute_line_total(base_price=15000, size_price=20000, modifier_prices=[3000], quantity=4)`
- **THEN** the result SHALL equal `92000` (= (20000 + 3000) × 4)

#### Scenario: Zero-price modifiers do not change the result
- **WHEN** calling `compute_line_total(base_price=10000, size_price=None, modifier_prices=[0, 0, 0], quantity=2)`
- **THEN** the result SHALL equal `20000`

#### Scenario: size_price of zero is still used instead of base_price
- **WHEN** calling `compute_line_total(base_price=15000, size_price=0, modifier_prices=[], quantity=1)`
- **THEN** the result SHALL equal `0` (explicit zero is not None)

#### Scenario: Negative inputs are rejected
- **WHEN** calling `compute_line_total(base_price=-1, size_price=None, modifier_prices=[], quantity=1)`
- **THEN** the function SHALL raise `ValueError`

#### Scenario: Zero or negative quantity is rejected
- **WHEN** calling `compute_line_total(base_price=15000, size_price=None, modifier_prices=[], quantity=0)`
- **THEN** the function SHALL raise `ValueError`

### Requirement: compute_subtotal sums line totals (PDD §7.2 step 1)

The system SHALL expose a pure function `compute_subtotal(line_totals: Iterable[int]) -> int` at `core_api.services.pricing` that returns the arithmetic sum of the provided integer kopecks values. An empty iterable SHALL return `0`. Any negative input SHALL raise `ValueError`.

#### Scenario: Empty cart yields zero subtotal
- **WHEN** calling `compute_subtotal([])`
- **THEN** the result SHALL equal `0`

#### Scenario: Multiple line totals sum correctly
- **WHEN** calling `compute_subtotal([10000, 25000, 5000])`
- **THEN** the result SHALL equal `40000`

#### Scenario: Negative line total is rejected
- **WHEN** calling `compute_subtotal([10000, -1])`
- **THEN** the function SHALL raise `ValueError`

### Requirement: pricing module has no framework or I/O dependencies

The `core_api.services.pricing` module SHALL import only from `typing`, `collections.abc`, and the Python standard library. It SHALL NOT import `sqlalchemy`, `redis`, `fastapi`, `pydantic`, or any `core_api.models.*` / `shared.models.*` symbol. This keeps the module re-usable by Phase 3 checkout without fan-out dependencies.

#### Scenario: Static import check
- **WHEN** parsing the AST of `services/core-api/src/core_api/services/pricing.py`
- **THEN** no `ImportFrom` node SHALL reference `sqlalchemy`, `redis`, `fastapi`, `pydantic`, `core_api.models`, or `shared.models`
