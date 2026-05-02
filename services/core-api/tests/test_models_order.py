"""RED: тесты SQLAlchemy-моделей Phase 3 в shared.models.

Покрывают 9 новых моделей (PDD §5.2): ShopSettings, Order, OrderItem, Payment,
Refund, LoyaltyTransaction, Promocode, PromocodeUsage, Notification — плюс 9
новых enum'ов в shared.enums.

Все импорты shared.models.* и shared.enums.* целевых классов выполняются ВНУТРИ
тел тестов: в RED-цикле они ещё не существуют, и импорт на уровне модуля сорвал
бы сбор всего файла. При ошибке мы хотим видеть провал конкретного теста.

Тесты на relationships/CASCADE требуют PostgreSQL и пропускаются на SQLite.
"""

from __future__ import annotations

import enum

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# ---------------------------------------------------------------------------
# 2. Enum-ы (shared.enums) — RED: все импорты ДОЛЖНЫ падать с ImportError
# ---------------------------------------------------------------------------

def test_order_status_enum_exists_with_correct_values() -> None:
    from shared.enums import OrderStatus

    assert issubclass(OrderStatus, str)
    assert issubclass(OrderStatus, enum.Enum)
    assert {e.value for e in OrderStatus} == {
        "created",
        "paid",
        "preparing",
        "ready",
        "in_delivery",
        "completed",
        "cancelled",
    }


def test_order_type_enum_exists_with_correct_values() -> None:
    from shared.enums import OrderType

    assert issubclass(OrderType, str)
    assert OrderType.PICKUP.value == "pickup"
    assert OrderType.DELIVERY.value == "delivery"
    assert len(list(OrderType)) == 2


def test_payment_status_enum_exists_with_correct_values() -> None:
    from shared.enums import PaymentStatus

    assert issubclass(PaymentStatus, str)
    assert {e.value for e in PaymentStatus} == {
        "pending",
        "awaiting_confirmation",
        "succeeded",
        "payment_failed",
        "refund_pending",
        "refunded",
        "refund_failed",
    }


def test_refund_status_enum_exists_with_correct_values() -> None:
    from shared.enums import RefundStatus

    assert issubclass(RefundStatus, str)
    assert {e.value for e in RefundStatus} == {"pending", "succeeded", "failed"}


def test_notification_channel_enum_exists_with_correct_values() -> None:
    from shared.enums import NotificationChannel

    assert issubclass(NotificationChannel, str)
    assert {e.value for e in NotificationChannel} == {"in_app", "sms"}


def test_notification_type_enum_exists_with_correct_values() -> None:
    from shared.enums import NotificationType

    assert issubclass(NotificationType, str)
    assert {e.value for e in NotificationType} == {"order_status_change", "otp"}


def test_notification_status_enum_exists_with_correct_values() -> None:
    from shared.enums import NotificationStatus

    assert issubclass(NotificationStatus, str)
    assert {e.value for e in NotificationStatus} == {"pending", "sent", "failed"}


def test_loyalty_transaction_type_enum_exists_with_correct_values() -> None:
    from shared.enums import LoyaltyTransactionType

    assert issubclass(LoyaltyTransactionType, str)
    assert {e.value for e in LoyaltyTransactionType} == {
        "accrual",
        "redemption",
        "reversal",
        "reservation",
        "admin_adjustment",
    }


def test_promocode_discount_type_enum_exists_with_correct_values() -> None:
    from shared.enums import PromocodeDiscountType

    assert issubclass(PromocodeDiscountType, str)
    assert {e.value for e in PromocodeDiscountType} == {"percent", "fixed_amount"}


# ---------------------------------------------------------------------------
# 3. ORM-мапперы: ShopSettings / Order / OrderItem
# ---------------------------------------------------------------------------

def _col_names(model) -> set[str]:
    mapper = sa_inspect(model)
    return {c.key for c in mapper.mapper.columns}


def _col_by_name(model, name: str):
    mapper = sa_inspect(model)
    return mapper.mapper.columns[name]


def _fk_referred_tables(model) -> set[str]:
    mapper = sa_inspect(model)
    tables: set[str] = set()
    for col in mapper.mapper.columns:
        for fk in col.foreign_keys:
            tables.add(fk.column.table.name)
    return tables


def test_shop_settings_model_declares_columns() -> None:
    from shared.models import ShopSettings

    mapper = sa_inspect(ShopSettings)
    assert mapper.mapper.mapped_table.name == "shop_settings"

    cols = _col_names(ShopSettings)
    required = {
        "id",
        "shop_lat",
        "shop_lon",
        "delivery_radius_km",
        "min_delivery_amount",
        "free_delivery_threshold",
        "delivery_fee",
        "loyalty_percent",
        "default_prep_time_minutes",
        "estimated_delivery_time_minutes",
        "working_hours",
        "updated_at",
    }
    assert cols >= required

    # id — целочисленный singleton-PK (а не UUID)
    id_col = _col_by_name(ShopSettings, "id")
    assert isinstance(id_col.type, (sa.Integer, sa.BigInteger))


def test_order_model_declares_columns() -> None:
    from shared.models import Order

    mapper = sa_inspect(Order)
    assert mapper.mapper.mapped_table.name == "orders"

    cols = _col_names(Order)
    required = {
        "id",
        "user_id",
        "status",
        "type",
        "requested_time",
        "estimated_ready_at",
        "delivery_address_snapshot",
        "subtotal",
        "discount_amount",
        "points_used",
        "delivery_fee",
        "total",
        "estimated_accrual",
        "promocode_id",
        "cancelled_by",
        "cancelled_at",
        "auto_completed",
        "auto_completed_at",
        "created_at",
        "updated_at",
    }
    assert cols >= required
    assert "users" in _fk_referred_tables(Order)


def test_order_user_fk_and_promocode_fk() -> None:
    from shared.models import Order

    referred = _fk_referred_tables(Order)
    assert "users" in referred
    assert "promocodes" in referred

    promocode_col = _col_by_name(Order, "promocode_id")
    assert promocode_col.nullable is True


def test_order_model_forbids_pii_columns() -> None:
    from shared.models import Order

    cols = _col_names(Order)
    forbidden = {"phone", "phone_hash", "customer_phone", "customer_name", "address_text"}
    leaked = cols & forbidden
    assert leaked == set(), (
        f"INV-013: PII-поля не должны быть на таблице orders напрямую — найдено: {leaked}"
    )


def test_order_item_model_declares_columns() -> None:
    from shared.models import OrderItem

    mapper = sa_inspect(OrderItem)
    assert mapper.mapper.mapped_table.name == "order_items"

    cols = _col_names(OrderItem)
    required = {
        "id",
        "order_id",
        "menu_item_id",
        "menu_item_name_ru",
        "menu_item_name_en",
        "size_option_id",
        "size_label",
        "unit_price",
        "modifiers_snapshot",
        "quantity",
        "line_total",
    }
    assert cols >= required
    assert "orders" in _fk_referred_tables(OrderItem)


def test_order_item_order_fk_restricts_physical_delete() -> None:
    from shared.models import OrderItem

    order_col = _col_by_name(OrderItem, "order_id")
    assert len(order_col.foreign_keys) >= 1
    fk = next(iter(order_col.foreign_keys))
    assert fk.column.table.name == "orders"
    assert (fk.ondelete or "").upper() == "RESTRICT"


def test_order_item_menu_item_id_is_not_fk() -> None:
    """INV-014 + §7.7: menu_item_id/size_option_id хранятся как reference для
    Repeat Order Chain, НЕ как FK. Иначе archive меню сломает историю."""
    from shared.models import OrderItem

    menu_item_col = _col_by_name(OrderItem, "menu_item_id")
    size_option_col = _col_by_name(OrderItem, "size_option_id")

    assert len(menu_item_col.foreign_keys) == 0, (
        "order_items.menu_item_id НЕ должен быть FK — только ссылка для Repeat Order Chain"
    )
    assert len(size_option_col.foreign_keys) == 0, (
        "order_items.size_option_id НЕ должен быть FK — только ссылка для Repeat Order Chain"
    )


def test_order_item_nullable_snapshot_references() -> None:
    from shared.models import OrderItem

    assert _col_by_name(OrderItem, "menu_item_id").nullable is True
    assert _col_by_name(OrderItem, "size_option_id").nullable is True

    for name in ("menu_item_name_ru", "menu_item_name_en", "unit_price", "line_total"):
        assert _col_by_name(OrderItem, name).nullable is False, f"{name} должен быть NOT NULL"


# ---------------------------------------------------------------------------
# 4. ORM-мапперы: Payment / Refund / LoyaltyTransaction / Promocode /
#    PromocodeUsage / Notification
# ---------------------------------------------------------------------------

def test_payment_model_declares_columns() -> None:
    from shared.models import Payment

    mapper = sa_inspect(Payment)
    assert mapper.mapper.mapped_table.name == "payments"

    cols = _col_names(Payment)
    assert cols >= {
        "id",
        "order_id",
        "yukassa_payment_id",
        "amount",
        "status",
        "confirmation_url",
        "idempotency_key",
        "created_at",
        "updated_at",
    }


def test_payment_order_fk_is_unique() -> None:
    """Payment ↔ Order — строго 1:1. Unique constraint или unique index на order_id."""
    from shared.models import Payment

    mapper = sa_inspect(Payment)
    table = mapper.mapper.mapped_table

    referred = _fk_referred_tables(Payment)
    assert "orders" in referred

    order_col = _col_by_name(Payment, "order_id")
    # unique=True на колонке либо отдельный UniqueConstraint/UniqueIndex на (order_id)
    has_col_unique = bool(order_col.unique)
    has_table_unique = any(
        isinstance(c, sa.UniqueConstraint) and [col.name for col in c.columns] == ["order_id"]
        for c in table.constraints
    )
    has_unique_index = any(
        idx.unique and [col.name for col in idx.columns] == ["order_id"]
        for idx in table.indexes
    )
    assert has_col_unique or has_table_unique or has_unique_index, (
        "payments.order_id должен быть UNIQUE (1:1 с orders)"
    )


def test_refund_model_declares_columns() -> None:
    from shared.models import Refund

    mapper = sa_inspect(Refund)
    assert mapper.mapper.mapped_table.name == "refunds"

    cols = _col_names(Refund)
    assert cols >= {
        "id",
        "payment_id",
        "yukassa_refund_id",
        "amount",
        "status",
        "reason",
        "created_at",
    }


def test_refund_payment_fk() -> None:
    from shared.models import Refund

    assert "payments" in _fk_referred_tables(Refund)


def test_loyalty_transaction_model_declares_columns() -> None:
    from shared.models import LoyaltyTransaction

    mapper = sa_inspect(LoyaltyTransaction)
    assert mapper.mapper.mapped_table.name == "loyalty_transactions"

    cols = _col_names(LoyaltyTransaction)
    assert cols >= {
        "id",
        "user_id",
        "order_id",
        "type",
        "amount",
        "balance_after",
        "description",
        "created_at",
    }

    assert _col_by_name(LoyaltyTransaction, "order_id").nullable is True


def test_promocode_model_declares_columns() -> None:
    from shared.models import Promocode

    mapper = sa_inspect(Promocode)
    assert mapper.mapper.mapped_table.name == "promocodes"

    cols = _col_names(Promocode)
    assert cols >= {
        "id",
        "code",
        "discount_type",
        "discount_value",
        "min_order_amount",
        "valid_from",
        "valid_until",
        "max_uses",
        "max_uses_per_user",
        "current_uses",
        "is_active",
        "created_at",
    }


def test_promocode_usage_model_declares_columns() -> None:
    from shared.models import PromocodeUsage

    mapper = sa_inspect(PromocodeUsage)
    assert mapper.mapper.mapped_table.name == "promocode_usages"

    cols = _col_names(PromocodeUsage)
    assert cols >= {"id", "promocode_id", "user_id", "order_id", "created_at"}

    referred = _fk_referred_tables(PromocodeUsage)
    assert {"promocodes", "users", "orders"} <= referred


def test_notification_model_declares_columns() -> None:
    from shared.models import Notification

    mapper = sa_inspect(Notification)
    assert mapper.mapper.mapped_table.name == "notifications"

    cols = _col_names(Notification)
    assert cols >= {
        "id",
        "user_id",
        "order_id",
        "channel",
        "type",
        "message_ru",
        "message_en",
        "status",
        "sent_at",
        "created_at",
    }

    assert _col_by_name(Notification, "order_id").nullable is True
    assert _col_by_name(Notification, "sent_at").nullable is True


# ---------------------------------------------------------------------------
# 5. Регистрация в shared.models.__all__
# ---------------------------------------------------------------------------

def test_phase3_models_registered_in_shared_models_all() -> None:
    import shared.models as shared_models

    expected = {
        "ShopSettings",
        "Order",
        "OrderItem",
        "Payment",
        "Refund",
        "LoyaltyTransaction",
        "Promocode",
        "PromocodeUsage",
        "Notification",
    }
    missing = expected - set(shared_models.__all__)
    assert missing == set(), f"Не зарегистрированы в shared.models.__all__: {missing}"
