"""DeliveryAssignment — привязка курьера к DELIVERY-заказу (PDD §6.3)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `delivery_assignments` table — 1:1 link
#            between a delivery-type Order and the courier handling it.
#   SCOPE:   order_id is UNIQUE (one assignment per order). courier_id is
#            nullable while the order sits in awaiting_courier. Status drives
#            the assignment state machine (awaiting_courier →
#            courier_assigned → picked_up → delivered | cancelled) per
#            PDD §6.3 / INV-016, mirrored by the corresponding *_at
#            timestamp columns.
#   DEPENDS: M-SHARED enums (DeliveryAssignmentStatus); SQLAlchemy 2.x ORM;
#            M-DATABASE Base; references orders.id and staff_accounts.id.
#   LINKS:   PDD §6.3 (delivery assignment state machine), INV-016,
#            docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeliveryAssignment - SQLAlchemy ORM class for `delivery_assignments`
#                        (PDD §6.3, INV-016)
# END_MODULE_MAP

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import DeliveryAssignmentStatus
from shared.models import Base


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # UNIQUE FK → orders.id: один заказ — одно назначение
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    # Nullable: пока курьер не взял заказ — NULL
    courier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("staff_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[DeliveryAssignmentStatus] = mapped_column(
        sa.Enum(
            DeliveryAssignmentStatus,
            name="delivery_assignment_status",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=DeliveryAssignmentStatus.AWAITING_COURIER,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    picked_up_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
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
