"""Phase 3 schema: orders, payments, refunds, loyalty, promocodes, notifications, shop_settings.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --- PG enum definitions (create_type=False на колонках, создаём вручную) ---

def _pg_enum(*values: str, name: str) -> PGEnum:
    """PG enum с create_type=False — тип создаётся вручную в upgrade()."""
    return PGEnum(*values, name=name, create_type=False)


order_status_enum = _pg_enum(
    "created", "paid", "preparing", "ready", "in_delivery", "completed", "cancelled",
    name="order_status",
)
order_type_enum = _pg_enum("pickup", "delivery", name="order_type")
payment_status_enum = _pg_enum(
    "pending", "awaiting_confirmation", "succeeded", "payment_failed",
    "refund_pending", "refunded", "refund_failed",
    name="payment_status",
)
refund_status_enum = _pg_enum("pending", "succeeded", "failed", name="refund_status")
notification_channel_enum = _pg_enum("in_app", "sms", name="notification_channel")
notification_type_enum = _pg_enum(
    "order_status_change", "otp", name="notification_type"
)
notification_status_enum = _pg_enum(
    "pending", "sent", "failed", name="notification_status"
)
loyalty_transaction_type_enum = _pg_enum(
    "accrual", "redemption", "reversal", "reservation", "admin_adjustment",
    name="loyalty_transaction_type",
)
promocode_discount_type_enum = _pg_enum(
    "percent", "fixed_amount", name="promocode_discount_type"
)

# Отдельные enum-объекты с create_type=True для ручного create()/drop() в up/down
_ENUM_CREATORS = [
    PGEnum(
        "created", "paid", "preparing", "ready", "in_delivery", "completed", "cancelled",
        name="order_status",
    ),
    PGEnum("pickup", "delivery", name="order_type"),
    PGEnum(
        "pending", "awaiting_confirmation", "succeeded", "payment_failed",
        "refund_pending", "refunded", "refund_failed",
        name="payment_status",
    ),
    PGEnum("pending", "succeeded", "failed", name="refund_status"),
    PGEnum("in_app", "sms", name="notification_channel"),
    PGEnum("order_status_change", "otp", name="notification_type"),
    PGEnum("pending", "sent", "failed", name="notification_status"),
    PGEnum(
        "accrual", "redemption", "reversal", "reservation", "admin_adjustment",
        name="loyalty_transaction_type",
    ),
    PGEnum("percent", "fixed_amount", name="promocode_discount_type"),
]

def upgrade() -> None:
    bind = op.get_bind()
    for e in _ENUM_CREATORS:
        e.create(bind, checkfirst=True)

    # --- shop_settings (singleton) ---
    op.create_table(
        "shop_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("shop_lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("shop_lon", sa.Numeric(10, 7), nullable=False),
        sa.Column("delivery_radius_km", sa.Numeric(6, 2), nullable=False),
        sa.Column("min_delivery_amount", sa.Integer(), nullable=False),
        sa.Column("free_delivery_threshold", sa.Integer(), nullable=False),
        sa.Column("delivery_fee", sa.Integer(), nullable=False),
        sa.Column("loyalty_percent", sa.Integer(), nullable=False),
        sa.Column("default_prep_time_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_delivery_time_minutes", sa.Integer(), nullable=False),
        sa.Column("working_hours", JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="ck_shop_settings_singleton"),
    )

    # --- promocodes (до orders: orders.promocode_id → promocodes.id) ---
    op.create_table(
        "promocodes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column(
            "discount_type",
            promocode_discount_type_enum,
            nullable=False,
        ),
        sa.Column("discount_value", sa.Integer(), nullable=False),
        sa.Column(
            "min_order_amount", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("max_uses_per_user", sa.Integer(), nullable=True),
        sa.Column("current_uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_promocodes_code"),
    )

    # --- orders ---
    op.create_table(
        "orders",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", order_status_enum, nullable=False, server_default="created"),
        sa.Column("type", order_type_enum, nullable=False),
        sa.Column("requested_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_address_snapshot", JSONB(), nullable=True),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivery_fee", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column(
            "estimated_accrual", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "promocode_id",
            UUID(as_uuid=True),
            sa.ForeignKey("promocodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cancelled_by", sa.String(32), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "auto_completed", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("auto_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- order_items ---
    op.create_table(
        "order_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # INV-014 + §7.7: ссылки, не FK
        sa.Column("menu_item_id", sa.BigInteger(), nullable=True),
        sa.Column("menu_item_name_ru", sa.String(200), nullable=False),
        sa.Column("menu_item_name_en", sa.String(200), nullable=False),
        sa.Column("size_option_id", sa.BigInteger(), nullable=True),
        sa.Column("size_label", sa.String(16), nullable=True),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("modifiers_snapshot", JSONB(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Integer(), nullable=False),
    )

    # --- payments (1:1 с orders через UNIQUE) ---
    op.create_table(
        "payments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("yukassa_payment_id", sa.String(64), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", payment_status_enum, nullable=False, server_default="pending"),
        sa.Column("confirmation_url", sa.String(500), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("order_id", name="uq_payments_order_id"),
        sa.UniqueConstraint("yukassa_payment_id", name="uq_payments_yukassa_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
    )

    # --- refunds ---
    op.create_table(
        "refunds",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "payment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("yukassa_refund_id", sa.String(64), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", refund_status_enum, nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("yukassa_refund_id", name="uq_refunds_yukassa_id"),
    )

    # --- loyalty_transactions (ledger) ---
    op.create_table(
        "loyalty_transactions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", loyalty_transaction_type_enum, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- promocode_usages ---
    op.create_table(
        "promocode_usages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "promocode_id",
            UUID(as_uuid=True),
            sa.ForeignKey("promocodes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("message_ru", sa.String(1000), nullable=False),
        sa.Column("message_en", sa.String(1000), nullable=False),
        sa.Column("status", notification_status_enum, nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- Indexes (PDD §5.4 Phase-3) ---
    op.create_index(
        "ix_orders_user_created_at",
        "orders",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_orders_active",
        "orders",
        ["status"],
        postgresql_where=sa.text("status NOT IN ('completed', 'cancelled')"),
    )
    op.create_index(
        "ix_orders_type_status",
        "orders",
        ["type", "status"],
    )
    op.create_index(
        "ix_promocode_usages_promocode_user",
        "promocode_usages",
        ["promocode_id", "user_id"],
    )
    op.create_index(
        "ix_loyalty_transactions_user_created_at",
        "loyalty_transactions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_notifications_user_created_at",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created_at", table_name="notifications")
    op.drop_index(
        "ix_loyalty_transactions_user_created_at", table_name="loyalty_transactions"
    )
    op.drop_index(
        "ix_promocode_usages_promocode_user", table_name="promocode_usages"
    )
    op.drop_index("ix_orders_type_status", table_name="orders")
    op.drop_index("ix_orders_active", table_name="orders")
    op.drop_index("ix_orders_user_created_at", table_name="orders")

    op.drop_table("notifications")
    op.drop_table("promocode_usages")
    op.drop_table("loyalty_transactions")
    op.drop_table("refunds")
    op.drop_table("payments")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("promocodes")
    op.drop_table("shop_settings")

    bind = op.get_bind()
    for e in reversed(_ENUM_CREATORS):
        e.drop(bind, checkfirst=True)
