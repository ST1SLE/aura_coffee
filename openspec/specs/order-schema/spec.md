# order-schema Specification

## Purpose
TBD - created by archiving change phase3-schema-green. Update Purpose after archive.
## Requirements
### Requirement: Phase 3 enums published from `shared.enums`

The `packages/shared/src/shared/enums.py` module SHALL export 9 new enum classes, each subclassing `str, enum.Enum`, with the exact lowercase string values mandated by PDD §5.2 / §6.1 / §6.2:

- `OrderStatus`: `created, paid, preparing, ready, in_delivery, completed, cancelled`
- `OrderType`: `pickup, delivery`
- `PaymentStatus`: `pending, awaiting_confirmation, succeeded, payment_failed, refund_pending, refunded, refund_failed`
- `RefundStatus`: `pending, succeeded, failed`
- `NotificationChannel`: `in_app, sms`
- `NotificationType`: `order_status_change, otp`
- `NotificationStatus`: `pending, sent, failed`
- `LoyaltyTransactionType`: `accrual, redemption, reversal, reservation, admin_adjustment`
- `PromocodeDiscountType`: `percent, fixed_amount`

#### Scenario: OrderStatus values match PDD §6.1
- **WHEN** a caller imports `OrderStatus` from `shared.enums`
- **THEN** `{e.value for e in OrderStatus}` MUST equal `{"created", "paid", "preparing", "ready", "in_delivery", "completed", "cancelled"}` and `issubclass(OrderStatus, str)` MUST be true

#### Scenario: OrderType covers pickup and delivery only
- **WHEN** a caller imports `OrderType` from `shared.enums`
- **THEN** it MUST have exactly two members whose values are `"pickup"` and `"delivery"`

### Requirement: Phase 3 SQLAlchemy models published from `shared.models`

The system SHALL provide 9 new declarative SQLAlchemy 2.0 models, each registered in `packages/shared/src/shared/models/__init__.py` `__all__`:

- `ShopSettings` (`shop_settings`): integer PK with `CHECK (id = 1)`; columns `id, shop_lat, shop_lon, delivery_radius_km, min_delivery_amount, free_delivery_threshold, delivery_fee, loyalty_percent, default_prep_time_minutes, estimated_delivery_time_minutes, working_hours` (JSONB), `updated_at`.
- `Order` (`orders`): UUID PK; FKs `user_id → users.id`, nullable `promocode_id → promocodes.id`; columns listed in PDD §5.2 Orders group; NO PII columns (INV-013).
- `OrderItem` (`order_items`): UUID PK; `order_id → orders.id ON DELETE CASCADE`; `menu_item_id` and `size_option_id` are nullable UUID columns WITHOUT foreign-key constraints (INV-014, §7.7); `menu_item_name_ru`, `menu_item_name_en`, `size_label`, `unit_price`, `modifiers_snapshot` (JSONB), `quantity`, `line_total` are non-nullable.
- `Payment` (`payments`): UUID PK; FK `order_id → orders.id` with a UNIQUE constraint enforcing 1:1; `yukassa_payment_id`, `amount`, `status`, `confirmation_url`, `idempotency_key`.
- `Refund` (`refunds`): UUID PK; FK `payment_id → payments.id`; `yukassa_refund_id`, `amount`, `status`, `reason`, `created_at`.
- `LoyaltyTransaction` (`loyalty_transactions`): UUID PK; `user_id → users.id`, nullable `order_id → orders.id`; `type`, `amount`, `balance_after`, `description`, `created_at`.
- `Promocode` (`promocodes`): UUID PK; UNIQUE `code`; `discount_type, discount_value, min_order_amount, valid_from, valid_until, max_uses, max_uses_per_user, current_uses, is_active, created_at`.
- `PromocodeUsage` (`promocode_usages`): UUID PK; FKs `promocode_id, user_id, order_id`; `created_at`.
- `Notification` (`notifications`): UUID PK; `user_id`, nullable `order_id`; `channel, type, message_ru, message_en, status`, nullable `sent_at`, `created_at`.

All timestamps SHALL be TIMESTAMPTZ. JSONB fields SHALL use SQLAlchemy's `JSONB` type.

#### Scenario: OrderItem snapshot contract
- **WHEN** a caller inspects `OrderItem.__table__` columns
- **THEN** `menu_item_id` and `size_option_id` MUST have zero `ForeignKey` constraints and MUST be nullable; `menu_item_name_ru`, `menu_item_name_en`, `unit_price`, `line_total` MUST be non-nullable

#### Scenario: order_items cascades on order deletion
- **WHEN** a caller inspects the FK from `order_items.order_id` to `orders.id`
- **THEN** `ondelete` MUST equal `"CASCADE"`

#### Scenario: payments 1:1 with orders
- **WHEN** a caller inspects `Payment.__table__`
- **THEN** `order_id` MUST have a UNIQUE constraint (or UNIQUE index) alongside its FK to `orders.id`

#### Scenario: Orders table has no PII
- **WHEN** a caller inspects `Order.__table__.columns.keys()`
- **THEN** the set MUST NOT contain any of `phone`, `phone_hash`, `customer_phone`, `customer_name`, `address_text` (INV-013)

#### Scenario: __all__ registration
- **WHEN** a caller reads `shared.models.__all__`
- **THEN** it MUST include `"ShopSettings"`, `"Order"`, `"OrderItem"`, `"Payment"`, `"Refund"`, `"LoyaltyTransaction"`, `"Promocode"`, `"PromocodeUsage"`, `"Notification"`

### Requirement: Pydantic v2 order schemas in `core_api.schemas.order`

The module `services/core-api/src/core_api/schemas/order.py` SHALL export:

- `CreateOrderRequest` — fields: `type: OrderType` (required), `delivery_address: DeliveryAddress | None = None` (nested Pydantic model with `text, lat, lon, apartment, entrance, floor, comment`), `requested_time: datetime | None = None`, `promocode_code: str | None = None`, `points_to_use: int = Field(default=0, ge=0)`. `model_config = ConfigDict(extra="forbid")` so unknown keys AND unknown enum values raise `ValidationError`.
- `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `OrderStatusUpdate` (field `new_status: OrderStatus`), `CancelOrderRequest` (field `reason: str | None = None`), `RepeatOrderResult` (fields `added_to_cart: int`, `skipped: list[SkippedItem]` where each skipped item has `name: str`, `reason: str`).
- Response models SHALL set `model_config = ConfigDict(from_attributes=True)` so that `model_validate(SimpleNamespace(...))` round-trips.

#### Scenario: CreateOrderRequest minimal pickup
- **WHEN** `CreateOrderRequest(type="pickup")` is constructed
- **THEN** validation MUST succeed, `type == OrderType.PICKUP`, `points_to_use == 0`, `delivery_address is None`

#### Scenario: CreateOrderRequest rejects unknown type
- **WHEN** `CreateOrderRequest(type="takeaway")` is constructed
- **THEN** a `pydantic.ValidationError` MUST be raised

#### Scenario: CreateOrderRequest rejects negative points
- **WHEN** `CreateOrderRequest(type="pickup", points_to_use=-1)` is constructed
- **THEN** a `pydantic.ValidationError` MUST be raised

#### Scenario: OrderItemResponse round-trips from ORM-like namespace
- **WHEN** a `SimpleNamespace` with `menu_item_name_ru`, `menu_item_name_en`, `size_label`, `unit_price`, `modifiers_snapshot`, `quantity`, `line_total` is passed to `OrderItemResponse.model_validate`
- **THEN** every field MUST be present on the resulting model with the original value

### Requirement: ShopSettingsResponse in `core_api.schemas.shop_settings`

The module `services/core-api/src/core_api/schemas/shop_settings.py` SHALL export `ShopSettingsResponse` exposing every field of the `shop_settings` table (`shop_lat`, `shop_lon`, `delivery_radius_km`, `min_delivery_amount`, `free_delivery_threshold`, `delivery_fee`, `loyalty_percent`, `default_prep_time_minutes`, `estimated_delivery_time_minutes`, `working_hours`, `updated_at`) with `model_config = ConfigDict(from_attributes=True)`.

#### Scenario: ShopSettingsResponse round-trips from namespace
- **WHEN** a `SimpleNamespace` with all canonical default values is passed to `ShopSettingsResponse.model_validate`
- **THEN** every field MUST round-trip with the original value

### Requirement: Alembic migration 0005 and shop_settings seed

`database/migrations/versions/0005_phase3_schema.py` SHALL:
- Create 9 PG enum types (`order_status, order_type, payment_status, refund_status, notification_channel, notification_type, notification_status, loyalty_transaction_type, promocode_discount_type`) with explicit names.
- Create 9 tables matching PDD §5.2, with TIMESTAMPTZ columns, JSONB snapshots, and all constraints described above.
- Create all PDD §5.4 Phase-3 indexes: `ix_orders_user_created_at` on `orders(user_id, created_at DESC)`; a partial `ix_orders_active` index on `orders(status)` where the `postgresql_where` predicate excludes `completed` and `cancelled`; `ix_orders_type_status` on `orders(type, status)`; UNIQUE `ix_promocodes_code` on `promocodes(code)`; `ix_promocode_usages_promocode_user` on `promocode_usages(promocode_id, user_id)`; `ix_loyalty_transactions_user_created_at` on `loyalty_transactions(user_id, created_at DESC)`; `ix_notifications_user_created_at` on `notifications(user_id, created_at DESC)`.
- Add a CHECK constraint `ck_shop_settings_singleton` on `shop_settings(id = 1)`.
- Downgrade: drop all 9 tables AND all 9 PG enum types so `pg_type` is clean.

`database/seeds/shop_settings.py` SHALL export `run(database_url: str) -> None` that opens its own engine, performs `INSERT ... ON CONFLICT (id) DO UPDATE` with the canonical defaults (`id=1, shop_lat=55.7558, shop_lon=37.6173, delivery_radius_km=5, min_delivery_amount=50000, free_delivery_threshold=150000, delivery_fee=20000, loyalty_percent=5, default_prep_time_minutes=15, estimated_delivery_time_minutes=30, working_hours` covering all 7 weekdays with open 08:00 / close 22:00), and commits. The script SHALL be idempotent.

#### Scenario: Upgrade creates all 9 tables
- **WHEN** `alembic upgrade head` is applied to a fresh PostgreSQL test DB at revision 0004
- **THEN** `shop_settings, orders, order_items, payments, refunds, loyalty_transactions, promocodes, promocode_usages, notifications` MUST be reflectable via SQLAlchemy `inspect()`

#### Scenario: Singleton CHECK blocks id != 1
- **WHEN** the test issues `INSERT INTO shop_settings (id, ...) VALUES (2, ...)`
- **THEN** PostgreSQL MUST raise an integrity error and the insert MUST NOT persist

#### Scenario: Active-orders partial index uses correct predicate
- **WHEN** the test reads reflected indexes for `orders` and locates the active-orders partial index
- **THEN** its `postgresql_where` predicate MUST reference both `completed` and `cancelled`

#### Scenario: Seed populates canonical defaults
- **WHEN** the test calls `database.seeds.shop_settings.run(TEST_DB_URL)` after `alembic upgrade head`
- **THEN** exactly one row with `id=1` and the exact PDD defaults above MUST exist

#### Scenario: Seed is idempotent
- **WHEN** `run(TEST_DB_URL)` is invoked twice consecutively
- **THEN** exactly one row MUST remain, matching the defaults

#### Scenario: Downgrade drops tables and enums
- **WHEN** `alembic downgrade 0004` is applied after `alembic upgrade head`
- **THEN** none of the 9 Phase 3 tables MUST remain, and none of the 9 Phase 3 PG enum types MUST remain in `pg_type`

