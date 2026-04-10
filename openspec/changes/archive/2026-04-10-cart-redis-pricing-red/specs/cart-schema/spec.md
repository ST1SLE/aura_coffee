## MODIFIED Requirements

_References: PDD §3 (Cart, Cart Item), PDD §5.3 (Redis keys — `cart:{session_id}`), INV-006 (stop list), INV-014 (order items are independent immutable snapshots)._

### Requirement: CartItemResponse DTO carries server-computed snapshot

The system SHALL expose a Pydantic v2 schema `CartItemResponse` at `core_api.schemas.cart` with fields: `line_id: str`, `menu_item_id: int`, `size_option_id: int | None`, `modifier_ids: list[int]`, `quantity: int`, `unit_price: int` (kopecks, `>= 0`), `line_total: int` (kopecks, `>= 0`), `menu_item_snapshot: MenuItemCartSnapshot`, `size_snapshot: SizeSnapshot | None`, `modifiers_snapshot: list[ModifierSnapshot]`. The snapshot sub-schemas SHALL carry bilingual names, prices, and availability flags sufficient for the cart UI without re-fetching the menu.

`line_id` SHALL be a lowercase hex string (16 characters) computed server-side as `sha1(f"{menu_item_id}|{size_option_id or 0}|{','.join(str(i) for i in sorted(modifier_ids))}").hexdigest()[:16]`. It SHALL be deterministic for a given `(menu_item_id, size_option_id, sorted(modifier_ids))` tuple and MUST be independent of `modifier_ids` ordering. The schema SHALL expose a helper `CartItemResponse.compute_line_id(menu_item_id, size_option_id, modifier_ids) -> str` usable by the cart service without instantiating the full response.

Clients SHALL NOT send `line_id` in any request body; it appears only in responses and path parameters. `CartItemCreate` remains unchanged.

_Previously:_ `CartItemResponse` exposed `menu_item_id`, `size_option_id`, `modifier_ids`, `quantity`, `unit_price`, `line_total`, `menu_item_snapshot`, `size_snapshot`, `modifiers_snapshot`. There was no stable identifier for the line, so PATCH/DELETE could only be keyed by array index.

_Now:_ the same fields plus `line_id: str` and a `compute_line_id(...)` classmethod.

_Note:_ These snapshots remain ephemeral cart-display helpers. They do NOT satisfy INV-014 — order items MUST still be independently rebuilt server-side at checkout in Phase 3.

#### Scenario: line_total equals unit_price times quantity
- **WHEN** `CartItemResponse` is populated with `unit_price=15000` and `quantity=3`
- **THEN** `line_total` SHALL equal `45000` (validator enforces invariant)

#### Scenario: Snapshot includes bilingual name
- **WHEN** inspecting `MenuItemCartSnapshot.model_fields`
- **THEN** both `name_ru` and `name_en` SHALL be present

#### Scenario: line_id is deterministic for the same inputs
- **WHEN** `CartItemResponse.compute_line_id(1, 3, [5, 7])` is called twice
- **THEN** both calls SHALL return the identical 16-character lowercase hex string

#### Scenario: line_id is independent of modifier order
- **WHEN** computing `compute_line_id(1, 3, [5, 7])` and `compute_line_id(1, 3, [7, 5])`
- **THEN** both SHALL return the identical value

#### Scenario: line_id changes when size_option_id changes
- **WHEN** computing `compute_line_id(1, 3, [5])` and `compute_line_id(1, 4, [5])`
- **THEN** the two results SHALL differ

#### Scenario: line_id changes when modifier set changes
- **WHEN** computing `compute_line_id(1, 3, [5])` and `compute_line_id(1, 3, [5, 7])`
- **THEN** the two results SHALL differ

#### Scenario: CartItemCreate does not expose line_id
- **WHEN** inspecting `CartItemCreate.model_fields`
- **THEN** there SHALL be no field named `line_id`
