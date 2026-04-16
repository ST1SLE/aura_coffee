## Context

The RED change `phase3-schema-red` landed 54 failing tests under `services/core-api/tests/`:
- `test_models_order.py` (26 tests) — enum values + SQLAlchemy mapper shape.
- `test_schemas_order.py` (13 tests) — Pydantic v2 request/response schemas.
- `test_migration_0005_phase3_schema.py` (15 tests) — Alembic DDL and shop_settings seed.

Affected modules: **[shared]**, **[core-api]**, **[database]**.

Current state: Phase 2 (Menu & Cart) schema is live via migration 0004; `shared.models` exposes `User`, `UserProfile`, `LoyaltyAccount`, `StaffAccount`, `Category`, `MenuItem`, `Modifier`, `SizeOption`. No order/payment/notification tables yet. `LoyaltyAccount` already owns the user's running balance; this change adds the **ledger** (`loyalty_transactions`) but does NOT move balance math out of `LoyaltyAccount`.

Authoritative references: PDD §5.2 (table list), §5.4 (indexes), §6.1 (order lifecycle), §6.2 (payment lifecycle), §7.7 (Repeat Order Chain), INV-004, INV-013, INV-014, INV-016.

## Goals / Non-Goals

**Goals:**
- Turn every RED test green by shipping 9 enums, 9 ORM models, 8 Pydantic schemas, 1 Alembic migration, and 1 seed script.
- Preserve the INV-014 snapshot contract on `order_items` (no FK to `menu_items`/`size_options`/`modifiers`, JSONB `modifiers_snapshot`).
- Preserve INV-013 PII isolation (no `phone`/`name`/raw-address columns outside `users`/`user_profiles`).
- Make migration 0005 forward-only and downgradable to 0004 with no residual PG enum types.
- Keep the `shop_settings` singleton invariant enforced at the DB level (`CHECK (id = 1)`).

**Non-Goals:**
- No HTTP endpoints (routers, dependencies, services) for Phase 3 — only data types.
- No loyalty balance math changes (`LoyaltyAccount.balance` is still updated by the future booking service, not this change).
- No YuKassa or SMS worker wiring.
- No admin UI changes.
- No automated fixture for "an order with items" in tests beyond what schema-level tests need.

## Decisions

### D1 — Enum values: lowercase snake_case, strings

PDD §5.2 dictates lowercase string values (`"created"`, `"in_delivery"`, `"payment_failed"`). Every enum MUST subclass `str, enum.Enum` so that Pydantic v2 coerces `"pickup"` → `OrderType.PICKUP` natively and SQLAlchemy serialises members as the string value (not the Python member name).

**Alternative rejected**: auto-generated uppercase values (`OrderStatus.CREATED.value == "CREATED"`) — would force every API client and SQL query to case-convert.

### D2 — One model per file under `shared/models/`

Follow the existing convention (`user.py`, `menu.py`) but break Phase 3 out file-by-file for blast radius: `shop_settings.py`, `order.py`, `order_item.py`, `payment.py`, `refund.py`, `loyalty_transaction.py`, `promocode.py`, `promocode_usage.py`, `notification.py`. The `__init__.py` imports every class and registers it in `__all__`, so `from shared.models import Order` still works.

**Alternative rejected**: one `phase3.py` with all 9 models — worse diff locality and breaks the 1-file-per-aggregate mental model.

### D3 — UUID PKs everywhere except `shop_settings`

Business tables use `UUID(as_uuid=True)` PKs with `server_default=sa.text("gen_random_uuid()")` (pgcrypto is already loaded by migration 0001). `shop_settings.id` is `Integer PRIMARY KEY` with `CHECK (id = 1)`, matching the PDD singleton requirement.

### D4 — `order_items` snapshot contract (INV-014)

`menu_item_id` and `size_option_id` on `order_items` are plain `UUID` columns, **nullable, no `ForeignKey`**. They carry enough information for §7.7 Repeat Order Chain to look up the current menu, and nullability means we don't break when a referenced menu item is archived. The authoritative order content lives in immutable non-nullable columns: `menu_item_name_ru`, `menu_item_name_en`, `size_label`, `unit_price`, `modifiers_snapshot` (JSONB), `quantity`, `line_total`.

**Mapper-level**: no `relationship(...)` between `OrderItem` and `MenuItem`/`SizeOption`/`Modifier`. The only relationship is `OrderItem.order` / `Order.items` with `ondelete="CASCADE"` on the FK — orders cascade, but individual items are never mutated.

### D5 — `payments` is 1:1 with `orders`

`payments.order_id` is NOT NULL with a UNIQUE constraint (named `uq_payments_order_id`) enforcing the 1:1 relationship PDD §5.2 prescribes. The idempotency key is a separate nullable unique column (`idempotency_key`), used by the payment-worker for at-most-once YuKassa creation.

### D6 — PG enum types with explicit names

Every PG enum type is created in the migration with an explicit `name=` (`order_status`, `order_type`, `payment_status`, `refund_status`, `notification_channel`, `notification_type`, `notification_status`, `loyalty_transaction_type`, `promocode_discount_type`) and `create_type=False` on column bindings so that the type is created once at the top of the upgrade and dropped individually on downgrade. This matches the RED test `test_downgrade_removes_phase3_tables_and_enums`.

### D7 — Migration is schema-only; seed is a standalone script

Per project rule, migration 0005 runs pure DDL. `database/seeds/shop_settings.py` exposes `run(database_url: str) -> None` that opens its own engine, opens a transaction, issues `INSERT ... ON CONFLICT (id) DO UPDATE` with all PDD defaults, and commits. The script is idempotent (repeated runs converge on the same single row) and is invoked separately by the RED test `test_shop_settings_seed_populates_defaults`.

### D8 — Indexes exactly match PDD §5.4

The migration creates named indexes:
- `ix_orders_user_created_at` on `orders(user_id, created_at DESC)`
- `ix_orders_active` on `orders(status)` with `postgresql_where=sa.text("status NOT IN ('completed', 'cancelled')")` (partial index for Kitchen dashboard lookups)
- `ix_orders_type_status` on `orders(type, status)`
- `ix_promocodes_code` UNIQUE on `promocodes(code)` (enforced by a UNIQUE constraint so it doubles as the lookup index)
- `ix_promocode_usages_promocode_user` on `promocode_usages(promocode_id, user_id)`
- `ix_loyalty_transactions_user_created_at` on `loyalty_transactions(user_id, created_at DESC)`
- `ix_notifications_user_created_at` on `notifications(user_id, created_at DESC)`

### D9 — Pydantic schemas use `ConfigDict(from_attributes=True)`

`OrderItemResponse`, `OrderResponse`, `ShopSettingsResponse` all use `model_config = ConfigDict(from_attributes=True)` so that the RED round-trip tests (`model_validate(SimpleNamespace(...))`) succeed. `CreateOrderRequest` uses `extra="forbid"` so that unknown keys fail validation alongside unknown enum values.

`CreateOrderRequest.points_to_use` is `int = Field(default=0, ge=0)` to reject negative values per RED `test_create_order_request_rejects_negative_points_to_use`.

## Risks / Trade-offs

- **[Risk] PG enum downgrade leaves orphan types** → Mitigation: downgrade explicitly issues `DROP TYPE` for each enum after dropping the dependent tables; covered by `test_downgrade_removes_phase3_tables_and_enums`.
- **[Risk] Snapshot columns diverge from menu wording** → Accepted trade-off (INV-014). Repeat Order Chain (§7.7) must reconcile on read, not on write.
- **[Risk] `order_items` rows could be orphaned by manual DB edits** → Mitigated by `ondelete=CASCADE`; manual edits are out of scope.
- **[Risk] CHECK (id = 1) blocks multi-location expansion** → Out of scope (single-location MVP). Future multi-location work would drop the check and add a `location_id` column.

## Migration Plan

1. `alembic upgrade head` on the target environment creates all 9 enums, all 9 tables, and all indexes in one transaction.
2. Operator then invokes `python -m database.seeds.shop_settings` (or equivalent) which calls `run(os.environ["DATABASE_URL"])` to install defaults. Idempotent — safe to re-run.
3. Rollback: `alembic downgrade 0004` drops every table and every PG enum introduced by 0005; shop_settings data is lost by design (defaults will be re-seeded on the next upgrade).
4. No data backfill needed — Phase 3 tables are empty on first deploy.

## 152-FZ Compliance

PII is confined to `users` and `user_profiles` (created in earlier phases). This change adds NO `phone`, `phone_hash`, `customer_name`, or raw `address_text` columns outside JSONB snapshots. The `orders.delivery_address_snapshot` JSONB is the only place where an address string lives on an order; the canonical contact channel (phone) is only reachable via `orders.user_id → users.phone_hash`. The RED test `test_order_model_forbids_pii_columns` enforces this at commit time.

## Atomicity Analysis (INV-004)

This change introduces the **schema** for atomic order creation but not the service code. The shape supports INV-004 because:
- `orders`, `order_items`, `payments`, `loyalty_transactions`, `promocode_usages` all share the same Alembic revision and live in the same PG schema, so a single SQLAlchemy session/transaction can span them without cross-DB coordination.
- `payments.order_id` has a UNIQUE constraint so the booking transaction cannot accidentally create two payments for one order even under concurrent retries.
- `promocodes.current_uses` lives on the promocode row itself, so the usage increment and the `promocode_usages` insert can be done with a single `UPDATE ... RETURNING` + `INSERT` inside the booking transaction.
- `loyalty_transactions.balance_after` captures the post-transaction balance; the booking service (future change) will perform `SELECT ... FOR UPDATE` on `loyalty_accounts` and insert the matching ledger row in the same transaction.

The booking-service logic is **out of scope** for this change — we only guarantee that the schema does not foreclose on atomicity.

## State Machine Reference (INV-016)

Schema columns align with PDD §6.1 and §6.2 transitions:
- `orders.status` — 7 values from §6.1 (`created → paid → preparing → ready → in_delivery → completed | cancelled`).
- `payments.status` — 7 values from §6.2 (`pending → awaiting_confirmation → succeeded | payment_failed; succeeded → refund_pending → refunded | refund_failed`).
- `refunds.status` — 3 values (`pending → succeeded | failed`).
- `orders.cancelled_by` (string) + `orders.cancelled_at` (TIMESTAMPTZ) capture the cancellation envelope from §6.1.
- `orders.auto_completed` + `orders.auto_completed_at` capture the auto-complete transition.

No state machine transitions are implemented in this change (service layer); only the storage shape is introduced.

## Open Questions

None at this stage — every field and index is pinned to a RED test or a PDD line item.
