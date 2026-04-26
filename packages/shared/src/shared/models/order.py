"""Order — заказы (PDD §5.2, §6.1)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `orders` table — the order header that
#            owns OrderItem snapshots and references Payment, Promocode and
#            (optionally) DeliveryAssignment.
#   SCOPE:   Status drives the canonical order state machine (PDD §6.1,
#            INV-016). delivery_address_snapshot is a JSONB PII-isolated
#            copy of the chosen DeliveryAddress at checkout (INV-013) so
#            later edits to the address book do not rewrite history.
#            Money fields (subtotal, discount_amount, points_used,
#            delivery_fee, total, estimated_accrual) are integer kopecks.
#   DEPENDS: M-SHARED enums (OrderStatus, OrderType); SQLAlchemy 2.x ORM;
#            M-DATABASE Base; references users.id and promocodes.id; owns
#            relationship to OrderItem.
#   LINKS:   PDD §5.2 (orders table), PDD §6.1 (order state machine),
#            INV-013, INV-014, INV-016, docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Order - SQLAlchemy ORM class for `orders` (PDD §6.1, INV-013/014/016)
# END_MODULE_MAP

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import OrderStatus, OrderType
from shared.models import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        sa.Enum(
            OrderStatus,
            name="order_status",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=OrderStatus.CREATED,
    )
    type: Mapped[OrderType] = mapped_column(
        sa.Enum(
            OrderType,
            name="order_type",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    requested_time: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    estimated_ready_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # Снимок адреса доставки (PII изолирован в JSONB per INV-013)
    delivery_address_snapshot: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True
    )
    subtotal: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    discount_amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    points_used: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    delivery_fee: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    total: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    estimated_accrual: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    promocode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("promocodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancelled_by: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    auto_completed: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False
    )
    auto_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.text("now()"),
    )

    items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
