## 1. Enums

- [x] 1.1 [shared] GREEN: append 9 enum classes (`OrderStatus`, `OrderType`, `PaymentStatus`, `RefundStatus`, `NotificationChannel`, `NotificationType`, `NotificationStatus`, `LoyaltyTransactionType`, `PromocodeDiscountType`) to `packages/shared/src/shared/enums.py`, each subclassing `str, enum.Enum` with the exact values from PDD §5.2/§6.1/§6.2. → passes RED 2.1–2.9 from `test_models_order.py`

## 2. SQLAlchemy models

- [x] 2.1 [shared] GREEN: create `packages/shared/src/shared/models/shop_settings.py` with `ShopSettings` (integer PK, CHECK `id=1` via `__table_args__`, columns per PDD §5.2 Settings group, JSONB `working_hours`, TIMESTAMPTZ `updated_at`). → passes RED 3.1
- [x] 2.2 [shared] GREEN: create `packages/shared/src/shared/models/order.py` with `Order` (UUID PK, `user_id→users.id` FK, nullable `promocode_id→promocodes.id` FK, JSONB `delivery_address_snapshot`, status/type PG enums, no PII columns). → passes RED 3.2, 3.3, 3.4
- [x] 2.3 [shared] GREEN: create `packages/shared/src/shared/models/order_item.py` with `OrderItem` (UUID PK, `order_id→orders.id ON DELETE CASCADE`, nullable `menu_item_id`/`size_option_id` as plain non-FK UUID columns, non-nullable snapshot fields + JSONB `modifiers_snapshot`). → passes RED 3.5, 3.6, 3.7, 3.8
- [x] 2.4 [shared] GREEN: create `packages/shared/src/shared/models/payment.py` with `Payment` (UUID PK, UNIQUE `order_id→orders.id`, `yukassa_payment_id`, `status` PG enum, `idempotency_key`). → passes RED 4.1, 4.2
- [x] 2.5 [shared] GREEN: create `packages/shared/src/shared/models/refund.py` with `Refund` (UUID PK, `payment_id→payments.id`, `status` PG enum). → passes RED 4.3, 4.4
- [x] 2.6 [shared] GREEN: create `packages/shared/src/shared/models/loyalty_transaction.py` with `LoyaltyTransaction` (UUID PK, `user_id→users.id`, nullable `order_id→orders.id`, `type` PG enum, `balance_after`). → passes RED 4.5
- [x] 2.7 [shared] GREEN: create `packages/shared/src/shared/models/promocode.py` with `Promocode` (UUID PK, UNIQUE `code`, `discount_type` PG enum, all config columns). → passes RED 4.6
- [x] 2.8 [shared] GREEN: create `packages/shared/src/shared/models/promocode_usage.py` with `PromocodeUsage` (UUID PK, three FKs). → passes RED 4.7
- [x] 2.9 [shared] GREEN: create `packages/shared/src/shared/models/notification.py` with `Notification` (UUID PK, nullable `order_id`, `channel/type/status` PG enums, nullable `sent_at`). → passes RED 4.8
- [x] 2.10 [shared] GREEN: update `packages/shared/src/shared/models/__init__.py` to import all 9 new classes and add their names to `__all__`. → passes RED 5.1

## 3. Pydantic schemas

- [x] 3.1 [core-api] GREEN: create `services/core-api/src/core_api/schemas/order.py` exporting `CreateOrderRequest` (with nested `DeliveryAddress`), `OrderItemResponse`, `OrderResponse`, `OrderListResponse`, `OrderStatusUpdate`, `CancelOrderRequest`, `RepeatOrderResult` (and a `SkippedItem` helper model). → passes RED 7.1, 7.3–7.12
- [x] 3.2 [core-api] GREEN: create `services/core-api/src/core_api/schemas/shop_settings.py` exporting `ShopSettingsResponse` with `ConfigDict(from_attributes=True)`. → passes RED 7.2, 7.13

## 4. Alembic migration

- [x] 4.1 [database] MIGRATE: create `database/migrations/versions/0005_phase3_schema.py` with `revision="0005"`, `down_revision="0004"`, creating 9 PG enum types, 9 tables (all constraints, CHECK singleton, CASCADE on `order_items.order_id`, UNIQUE on `payments.order_id`), and all PDD §5.4 Phase-3 indexes (incl. the partial active-orders index). The downgrade drops every table and every PG enum type introduced. → passes RED 8.1, 8.3–8.12, 8.15
- [x] 4.2 [database] MIGRATE: in 0005, name the singleton CHECK `ck_shop_settings_singleton` and assert the error path works (`id != 1` rejected). → passes RED 8.2

## 5. Shop settings seed

- [x] 5.1 [database] GREEN: create `database/seeds/shop_settings.py` exporting `run(database_url: str) -> None` that opens its own engine, performs `INSERT ... ON CONFLICT (id) DO UPDATE` with the canonical PDD defaults, commits, and is idempotent. Include an `if __name__ == "__main__":` block that reads `os.environ["DATABASE_URL"]`. → passes RED 8.13, 8.14

## 6. Verify

- [x] 6.1 [core-api] VERIFY: run `pytest services/core-api/tests/test_models_order.py services/core-api/tests/test_schemas_order.py services/core-api/tests/test_migration_0005_phase3_schema.py -v` (in Docker via `docker compose exec -T core-api pytest ...`); confirm every RED test now passes (sqlite-skipped tests are acceptable as skips).
- [x] 6.2 [core-api] VERIFY: run `pytest services/core-api/tests/` (full suite) and confirm no Phase-1/Phase-2 regressions.
- [x] 6.3 [database] VERIFY: run `alembic upgrade head` on a fresh PG and assert `alembic downgrade 0004` returns the DB to the pre-Phase-3 shape with no orphan PG enum types.
