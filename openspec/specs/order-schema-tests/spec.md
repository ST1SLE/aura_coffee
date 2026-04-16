# order-schema-tests Specification

## Purpose
TBD - created by archiving change phase3-schema-red. Update Purpose after archive.
## Requirements
### Requirement: RED suite for Phase 3 enums

The system SHALL provide pytest tests that import every Phase 3 enum from `shared.enums` and assert that each enum declares the exact value strings mandated by the PDD. The enum names and values SHALL be: `OrderStatus` (`created, paid, preparing, ready, in_delivery, completed, cancelled`), `OrderType` (`pickup, delivery`), `PaymentStatus` (`pending, awaiting_confirmation, succeeded, payment_failed, refund_pending, refunded, refund_failed`), `RefundStatus` (`pending, succeeded, failed`), `NotificationChannel` (`in_app, sms`), `NotificationType` (`order_status_change, otp`), `NotificationStatus` (`pending, sent, failed`), `LoyaltyTransactionType` (`accrual, redemption, reversal, reservation, admin_adjustment`), `PromocodeDiscountType` (`percent, fixed_amount`). Each enum MUST subclass `str, enum.Enum`.

#### Scenario: Enum import fails at test runtime
- **WHEN** a test imports an enum name that does not yet exist in `shared.enums` (RED state)
- **THEN** the individual test MUST fail with `ImportError` or `AttributeError`, while other tests in the same module continue to run independently.

#### Scenario: Enum value mismatch surfaces as test failure
- **WHEN** `shared.enums.OrderStatus` exists but the set of `.value` attributes does not match `{"created", "paid", "preparing", "ready", "in_delivery", "completed", "cancelled"}`
- **THEN** the test MUST fail with an assertion error naming the missing or extra values.

### Requirement: RED suite for Phase 3 SQLAlchemy models

The system SHALL provide pytest tests that import every new model (`ShopSettings`, `Order`, `OrderItem`, `Payment`, `Refund`, `LoyaltyTransaction`, `Promocode`, `PromocodeUsage`, `Notification`) from `shared.models` and assert: column names cover every field in PDD §5.2, primary keys are UUID for business tables and `Integer` for `ShopSettings`, foreign keys point to the correct referred tables with the correct `ondelete` behavior (`CASCADE` for `order_items.order_id`), nullable flags match the spec, and enum-typed columns use PG enum type names matching `order_status`, `order_type`, `payment_status`, `refund_status`, `notification_channel`, `notification_type`, `notification_status`, `loyalty_transaction_type`, `promocode_discount_type`. All 9 models SHALL be registered in `packages/shared/src/shared/models/__init__.py` `__all__`.

#### Scenario: Missing model class
- **WHEN** a test does `from shared.models.order import Order` and `Order` does not exist yet
- **THEN** the test MUST fail; other model tests in the same file MUST still be collected and run.

#### Scenario: Missing or mis-typed FK
- **WHEN** `OrderItem.order_id` exists but does not reference `orders.id`, or its `ondelete` is not `CASCADE`
- **THEN** the test MUST fail with an assertion error that names the expected FK target.

#### Scenario: PII leakage into order tables (INV-013)
- **WHEN** any new table other than `users` / `user_profiles` declares a `phone`, `phone_hash`, `name`, or raw `address_text` column at the top level (JSONB snapshot fields excepted)
- **THEN** the corresponding RED test MUST fail.

### Requirement: RED suite for order-items immutability contract

The system SHALL provide a RED test that asserts `OrderItem` exposes only a snapshot contract: `menu_item_id` and `size_option_id` on the ORM model are nullable non-FK columns (stored for Repeat Order Chain §7.7 lookup), and the immutable textual fields `menu_item_name_ru`, `menu_item_name_en`, and `modifiers_snapshot` (JSONB) exist and are non-nullable. No SQLAlchemy `relationship(...)` between `OrderItem` and `MenuItem` / `SizeOption` / `Modifier` SHALL exist, preventing cascading updates from menu mutations.

#### Scenario: menu_item_id is a plain column, not a FK
- **WHEN** the RED test inspects `OrderItem.menu_item_id` and finds a `ForeignKey` constraint on it
- **THEN** the test MUST fail, signalling that the snapshot contract is violated (Repeat Order Chain would then break when a menu item is archived).

#### Scenario: Missing JSONB modifier snapshot
- **WHEN** `OrderItem.modifiers_snapshot` is not declared, or its column type is not JSONB
- **THEN** the RED test MUST fail.

### Requirement: RED suite for Pydantic order schemas

The system SHALL provide pytest tests for `core_api.schemas.order` declaring: `CreateOrderRequest` (`type: OrderType`, optional nested `delivery_address` with `text, lat, lon, apartment, entrance, floor, comment`, optional `requested_time`, optional `promocode_code`, optional `points_to_use` defaulting to 0), `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `OrderStatusUpdate`, `CancelOrderRequest`, `RepeatOrderResult`. Tests MUST exercise: required vs optional fields, default values, enum coercion, and that `CreateOrderRequest` rejects unknown `type` values with a `pydantic.ValidationError`.

#### Scenario: CreateOrderRequest accepts minimal pickup
- **WHEN** a test constructs `CreateOrderRequest(type="pickup")` against the (eventually-built) schema
- **THEN** validation succeeds and `points_to_use == 0` by default.

#### Scenario: CreateOrderRequest rejects unknown type
- **WHEN** a test constructs `CreateOrderRequest(type="takeaway")` (not a member of `OrderType`)
- **THEN** a `pydantic.ValidationError` MUST be raised.

#### Scenario: RepeatOrderResult counts added and skipped
- **WHEN** a test constructs `RepeatOrderResult(added_to_cart=3, skipped=[{"name": "Latte", "reason": "stop_list"}])`
- **THEN** validation succeeds; `added_to_cart` is `int`, `skipped` is a `list` of objects with `name` and `reason`.

### Requirement: RED suite for ShopSettingsResponse

The system SHALL provide a pytest test that `core_api.schemas.shop_settings.ShopSettingsResponse` is a `pydantic.BaseModel` exposing every field from the `shop_settings` model (`shop_lat`, `shop_lon`, `delivery_radius_km`, `min_delivery_amount`, `free_delivery_threshold`, `delivery_fee`, `loyalty_percent`, `default_prep_time_minutes`, `estimated_delivery_time_minutes`, `working_hours`, `updated_at`) and validates successfully when fed a `SimpleNamespace` matching the ORM row shape.

#### Scenario: ShopSettingsResponse round-trips from ORM-like namespace
- **WHEN** a test builds a `SimpleNamespace` with the canonical default values and calls `ShopSettingsResponse.model_validate(ns)`
- **THEN** the resulting model MUST expose every listed field with the original values.

### Requirement: RED suite for migration 0005 and shop_settings seed

The system SHALL provide pytest tests that: (a) call `alembic upgrade head` against a real PostgreSQL test database (skipped when `TEST_DATABASE_URL` points at SQLite); (b) assert every Phase 3 table exists with the columns listed in PDD §5.2; (c) assert every index listed in PDD §5.4 exists — `orders(user_id, created_at DESC)`, a partial `orders(status) WHERE status NOT IN ('completed', 'cancelled')` index, `orders(type, status)`, `promocodes(code)` UNIQUE, `promocode_usages(promocode_id, user_id)`, `loyalty_transactions(user_id, created_at DESC)`, `notifications(user_id, created_at DESC)`; (d) assert the `CHECK (id = 1)` constraint on `shop_settings` rejects inserts with `id != 1`; (e) invoke `database.seeds.shop_settings.run(TEST_DATABASE_URL)` and assert the resulting singleton row has the exact default values documented in the task brief; (f) the downgrade step (`alembic downgrade 0004`) removes every Phase 3 table and PG enum introduced by migration 0005.

#### Scenario: Schema upgrade creates all tables
- **WHEN** `alembic upgrade head` is applied to an empty test database
- **THEN** `shop_settings`, `orders`, `order_items`, `payments`, `refunds`, `loyalty_transactions`, `promocodes`, `promocode_usages`, `notifications` MUST be reflectable via SQLAlchemy `inspect()`.

#### Scenario: Active-orders partial index uses correct predicate
- **WHEN** the test reads reflected indexes of `orders` and locates the Phase-3 active-orders partial index
- **THEN** its `postgresql_where` predicate MUST mention both `completed` and `cancelled` as excluded statuses.

#### Scenario: Singleton CHECK blocks non-1 id
- **WHEN** the test issues `INSERT INTO shop_settings (id, ...) VALUES (2, ...)`
- **THEN** the database MUST raise an integrity error, the transaction MUST roll back, and the test MUST assert the error surfaced.

#### Scenario: Seed populates canonical defaults
- **WHEN** the test calls `database.seeds.shop_settings.run(TEST_DATABASE_URL)` after `alembic upgrade head`
- **THEN** the sole row in `shop_settings` MUST have `id = 1`, `shop_lat = 55.7558`, `shop_lon = 37.6173`, `delivery_radius_km = 5`, `min_delivery_amount = 50000`, `free_delivery_threshold = 150000`, `delivery_fee = 20000`, `loyalty_percent = 5`, `default_prep_time_minutes = 15`, `estimated_delivery_time_minutes = 30`, and `working_hours` containing all 7 weekday keys with `open = "08:00"` and `close = "22:00"`.

#### Scenario: Downgrade leaves database at revision 0004
- **WHEN** the test runs `alembic upgrade head` followed by `alembic downgrade 0004`
- **THEN** none of the 9 Phase 3 tables remain, and the Phase 3 PG enum types (`order_status`, `order_type`, `payment_status`, `refund_status`, `notification_channel`, `notification_type`, `notification_status`, `loyalty_transaction_type`, `promocode_discount_type`) MUST be dropped.

