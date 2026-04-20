"""Phase 4: delivery_assignments — привязка курьера к DELIVERY-заказу (PDD §6.3).

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


delivery_assignment_status_enum = PGEnum(
    "awaiting_courier",
    "courier_assigned",
    "picked_up",
    "delivered",
    "cancelled",
    name="delivery_assignment_status",
    create_type=False,
)

_ENUM_CREATOR = PGEnum(
    "awaiting_courier",
    "courier_assigned",
    "picked_up",
    "delivered",
    "cancelled",
    name="delivery_assignment_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    _ENUM_CREATOR.create(bind, checkfirst=True)

    op.create_table(
        "delivery_assignments",
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
        sa.Column(
            "courier_id",
            UUID(as_uuid=True),
            sa.ForeignKey("staff_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            delivery_assignment_status_enum,
            nullable=False,
            server_default="awaiting_courier",
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("order_id", name="uq_delivery_assignments_order_id"),
    )

    # Частичный индекс на AWAITING_COURIER — для GET /assignments/available
    op.create_index(
        "ix_delivery_assignments_awaiting",
        "delivery_assignments",
        ["status"],
        postgresql_where=sa.text("status = 'awaiting_courier'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delivery_assignments_awaiting", table_name="delivery_assignments"
    )
    op.drop_table("delivery_assignments")

    bind = op.get_bind()
    _ENUM_CREATOR.drop(bind, checkfirst=True)
