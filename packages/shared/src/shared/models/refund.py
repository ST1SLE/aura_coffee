"""Refund — возвраты через YuKassa (PDD §5.2, §6.2)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `refunds` table — YuKassa refund linked
#            to a Payment, with its own dispatch state machine.
#   SCOPE:   Each refund references one payment_id (multiple partial refunds
#            allowed). Status follows pending → succeeded | failed per
#            PDD §6.2 / INV-016. yukassa_refund_id is UNIQUE so webhook
#            replays are idempotent.
#   DEPENDS: M-SHARED enums (RefundStatus); SQLAlchemy 2.x ORM; M-DATABASE
#            Base; references payments.id.
#   LINKS:   PDD §5.2 (refunds table), PDD §6.2 (refund state machine),
#            INV-016, docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Refund - SQLAlchemy ORM class for `refunds` (PDD §6.2, INV-016)
# END_MODULE_MAP

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import RefundStatus
from shared.models import Base


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    yukassa_refund_id: Mapped[str | None] = mapped_column(
        sa.String(64), nullable=True, unique=True
    )
    amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        sa.Enum(
            RefundStatus,
            name="refund_status",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=RefundStatus.PENDING,
    )
    reason: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
