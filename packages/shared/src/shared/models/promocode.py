"""Promocode — промокоды (PDD §5.2)."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import PromocodeDiscountType
from shared.models import Base


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    discount_type: Mapped[PromocodeDiscountType] = mapped_column(
        sa.Enum(
            PromocodeDiscountType,
            name="promocode_discount_type",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    discount_value: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    min_order_amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    valid_from: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    max_uses: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    max_uses_per_user: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    current_uses: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
