## Why

The RED change `phase3-schema-red` delivered 54 failing tests covering Phase 3 enums, SQLAlchemy models, Pydantic schemas, Alembic migration 0005, and the shop_settings seed. This GREEN change implements the production code that turns those tests green, unlocking the Phase 3 (Order & Payment) backend surface described in PDD §5.2, §5.4, §6.1, §6.2.

## What Changes

- Add 9 new enums to `packages/shared/src/shared/enums.py`: `OrderStatus`, `OrderType`, `PaymentStatus`, `RefundStatus`, `NotificationChannel`, `NotificationType`, `NotificationStatus`, `LoyaltyTransactionType`, `PromocodeDiscountType` (all `str, enum.Enum` with lowercase values per PDD).
- Add 9 new SQLAlchemy 2.0 models in `packages/shared/src/shared/models/`: `ShopSettings` (integer singleton with `CHECK (id = 1)`), `Order`, `OrderItem`, `Payment`, `Refund`, `LoyaltyTransaction`, `Promocode`, `PromocodeUsage`, `Notification`. All use UUID PKs (except `ShopSettings`), TIMESTAMPTZ timestamps, JSONB for snapshots, and bilingual `*_ru`/`*_en` columns where required.
- Enforce INV-014 snapshot contract: `OrderItem.menu_item_id` and `OrderItem.size_option_id` are plain nullable columns (no FK), textual name/price fields are non-nullable.
- Enforce INV-013 PII isolation: no `phone`, `name`, or raw address columns on any Phase 3 table (addresses live in `delivery_address_snapshot` JSONB).
- Register every new model in `packages/shared/src/shared/models/__init__.py` `__all__`.
- Add Pydantic v2 schemas to `services/core-api/src/core_api/schemas/order.py` (`CreateOrderRequest`, `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `OrderStatusUpdate`, `CancelOrderRequest`, `RepeatOrderResult`) and `services/core-api/src/core_api/schemas/shop_settings.py` (`ShopSettingsResponse`).
- Add Alembic migration `database/migrations/versions/0005_phase3_schema.py` that creates all 9 PG enum types, all 9 tables, and the PDD §5.4 indexes (incl. the partial active-orders index); the downgrade drops them all.
- Add standalone seed script `database/seeds/shop_settings.py` with `run(database_url)` idempotently upserting the singleton row with PDD defaults.

## Capabilities

### New Capabilities
- `order-schema`: Domain data model for Phase 3 (Order & Payment): enums, ORM models, Pydantic schemas, migration, and singleton seed.

### Modified Capabilities
<!-- None — RED tests were declared as an independent capability `order-schema-tests`, which is untouched here. -->

## Impact

- **Code**: `packages/shared/src/shared/enums.py`, `packages/shared/src/shared/models/{shop_settings,order,order_item,payment,refund,loyalty_transaction,promocode,promocode_usage,notification}.py`, `packages/shared/src/shared/models/__init__.py`, `services/core-api/src/core_api/schemas/{order,shop_settings}.py`, `database/migrations/versions/0005_phase3_schema.py`, `database/seeds/shop_settings.py`.
- **APIs**: No HTTP endpoints change in this cycle — only the data-model surface that Phase 3 endpoints (next cycles) will consume.
- **Database**: Introduces 9 tables and 9 PG enum types; downgrade to 0004 is exercised in tests.
- **Dependencies**: No new runtime dependencies.

## Non-Goals

- No HTTP endpoints, routers, or services for orders/payments/refunds/loyalty/promocodes (subsequent Phase 3 changes).
- No YuKassa client wiring or webhook handlers.
- No Celery tasks for payment polling or notifications.
- No admin UI for promocodes or shop settings.
- No loyalty balance calculation service — only the ledger table.
- No delivery zone validation — Phase 4 territory.

## MVP Phase

Phase 3 — Order & Payment (PDD §7.1).
