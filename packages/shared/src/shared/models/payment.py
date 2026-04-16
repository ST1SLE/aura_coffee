"""Payment — платёж YuKassa 1:1 с заказом (PDD §5.2, §6.2)."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import PaymentStatus
from shared.models import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # UNIQUE: один платёж на заказ (1:1 per PDD §5.2)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    yukassa_payment_id: Mapped[str | None] = mapped_column(
        sa.String(64), nullable=True, unique=True
    )
    amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        sa.Enum(
            PaymentStatus,
            name="payment_status",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    confirmation_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        sa.String(64), nullable=True, unique=True
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
