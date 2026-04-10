## ADDED Requirements

_References: PDD §3 (Cart, Cart Item), PDD §5.3 (Redis keys — `cart:{session_id}`), INV-006 (stop list), INV-014 (order items are independent immutable snapshots)._

### Requirement: CartItemCreate DTO for add/update operations

The system SHALL expose a Pydantic v2 schema `CartItemCreate` at `core_api.schemas.cart` with fields: `menu_item_id: int`, `size_option_id: int | None`, `modifier_ids: list[int]` (default `[]`), `quantity: int` with `Field(ge=1, le=99)`. It SHALL NOT contain any price, name, or snapshot fields — prices MUST always be computed server-side per INV-006.

#### Scenario: Quantity below 1 is rejected
- **WHEN** constructing `CartItemCreate(menu_item_id=1, quantity=0)`
- **THEN** Pydantic SHALL raise `ValidationError`

#### Scenario: Quantity above 99 is rejected
- **WHEN** constructing `CartItemCreate(menu_item_id=1, quantity=100)`
- **THEN** Pydantic SHALL raise `ValidationError`

#### Scenario: No price fields are accepted from clients
- **WHEN** inspecting `CartItemCreate.model_fields`
- **THEN** there SHALL be no fields named `unit_price`, `line_total`, `price`, or similar

### Requirement: CartItemResponse DTO carries server-computed snapshot

The system SHALL expose a Pydantic v2 schema `CartItemResponse` at `core_api.schemas.cart` with fields: `menu_item_id: int`, `size_option_id: int | None`, `modifier_ids: list[int]`, `quantity: int`, `unit_price: int` (kopecks, `>= 0`), `line_total: int` (kopecks, `>= 0`), `menu_item_snapshot: MenuItemCartSnapshot`, `size_snapshot: SizeSnapshot | None`, `modifiers_snapshot: list[ModifierSnapshot]`. The snapshot sub-schemas SHALL carry bilingual names, prices, and availability flags sufficient for the cart UI without re-fetching the menu.

_Note:_ These snapshots are ephemeral cart-display helpers. They do NOT satisfy INV-014 — order items MUST be independently rebuilt server-side at checkout in Phase 3.

#### Scenario: line_total equals unit_price times quantity
- **WHEN** `CartItemResponse` is populated with `unit_price=15000` and `quantity=3`
- **THEN** `line_total` SHALL equal `45000` (validator enforces invariant)

#### Scenario: Snapshot includes bilingual name
- **WHEN** inspecting `MenuItemCartSnapshot.model_fields`
- **THEN** both `name_ru` and `name_en` SHALL be present

### Requirement: CartResponse aggregates items with totals

The system SHALL expose a Pydantic v2 schema `CartResponse` at `core_api.schemas.cart` with fields: `items: list[CartItemResponse]`, `subtotal: int` (kopecks, `>= 0`), `currency: Literal["RUB"]`, `expires_at: datetime`. The `subtotal` field SHALL equal the sum of `line_total` across all items (enforced by validator). This schema is a **response-only** contract — it does not define how the cart is stored (Redis key layout is out of scope for this change).

#### Scenario: Subtotal matches sum of line totals
- **WHEN** a `CartResponse` is constructed with items having line totals `[10000, 25000, 5000]`
- **THEN** `subtotal` SHALL equal `40000` or validation SHALL fail

#### Scenario: Currency is locked to RUB
- **WHEN** attempting to construct `CartResponse(currency="USD", ...)`
- **THEN** Pydantic SHALL raise `ValidationError`

### Requirement: Cart DTOs do not leak ORM or Redis concerns

Cart schemas SHALL NOT import from `core_api.models.*`, `sqlalchemy`, or any Redis client library. They SHALL depend only on `pydantic`, `shared.enums`, and the standard library.

#### Scenario: Schemas module imports are limited
- **WHEN** inspecting the imports of `core_api.schemas.cart`
- **THEN** no imports from `sqlalchemy`, `redis`, `core_api.models`, or `core_api.database` SHALL be present
