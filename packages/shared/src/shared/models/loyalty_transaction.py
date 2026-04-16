"""LoyaltyTransaction — ledger начислений/списаний баллов (PDD §5.2)."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import LoyaltyTransactionType
from shared.models import Base


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Админские корректировки могут быть без order_id
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[LoyaltyTransactionType] = mapped_column(
        sa.Enum(
            LoyaltyTransactionType,
            name="loyalty_transaction_type",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    balance_after: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
