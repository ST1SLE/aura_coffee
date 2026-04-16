"""Refund — возвраты через YuKassa (PDD §5.2, §6.2)."""

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
