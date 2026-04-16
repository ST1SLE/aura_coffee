## Why

Customers need to see their past orders and quickly re-order a previous combination without navigating the menu. PDD §7.7 specifies the "Повторить заказ" flow: load a historical order, re-populate the cart with currently available items at current prices, skip unavailable items with user-visible notifications. This is the RED phase of the two-change model — failing tests lock the contract before implementation.

MVP phase: **Phase 3 — Order & Payment** (PDD §7.1).

## What Changes

- Introduce failing tests for a new order-history service (`list_orders`) covering pagination, ordering, user isolation, joined `order_items` load, and total_count.
- Introduce failing tests for a new order-repeat service (`repeat_order`) covering ownership check, current-price re-cart, stop-list skip, archived skip, deleted menu item skip, size-option unavailability (entire item skip), modifier unavailability (modifier-only skip), all-unavailable error, and notification content.
- Introduce failing router tests for `GET /api/v1/orders` (paginated history) and `POST /api/v1/orders/{order_id}/repeat`, asserting CUSTOMER auth, per-user isolation, `per_page` cap at 50, and that repeat does NOT auto-checkout.
- No service, router, or schema code in this change. No registration in `main.py`. Tests MUST fail because implementation does not exist yet.

## Capabilities

### New Capabilities
- `order-history`: Customer-facing paginated listing of own past orders, including line items snapshot.
- `order-repeat`: Re-populate cart from a historical order using current availability and current prices, with per-item/per-modifier skip notifications; never auto-checkouts.

### Modified Capabilities
<!-- None — RED phase only introduces new failing tests for new capabilities. -->

## Non-Goals

- Implementing the services, routers, or wiring in `main.py` (that is the GREEN phase).
- Duplicating `GET /api/v1/orders/{order_id}` — single-order detail is owned by the order-checkout feature (`routers/orders.py`).
- Adding new fields/migrations to `order_items` — `menu_item_id` and `size_option_id` non-FK references already exist (`phase3-schema`).
- Frontend UI for history/repeat (separate frontend change).
- Automatic checkout after repeat — PDD §7.7 explicitly requires the client to review the cart.
- Cross-user sharing or admin views of order history.

## Impact

- **Code**: adds new test modules under `services/core-api/tests/` (`test_order_history*.py`, `test_order_repeat*.py`, `test_route_order_history*.py`). May extend shared test fixtures/conftest helpers for seeding historical orders.
- **APIs**: locks the contract for `GET /api/v1/orders` and `POST /api/v1/orders/{order_id}/repeat` (no implementation yet).
- **Dependencies**: reuses `CartService.add_item` (services/cart.py) and SQLAlchemy ORM models from phase3-schema. No new third-party packages.
- **Inviolable rules touched**: INV-002 (auth on mutations — repeat), INV-013 (PII isolation — history reads user-scoped data by UUID), INV-014 (order items immutable — repeat reads snapshot, writes to cart not to items).
- **Systems**: Redis (cart writes via CartService) and PostgreSQL (read-only joined loads on orders/order_items). No migrations.
