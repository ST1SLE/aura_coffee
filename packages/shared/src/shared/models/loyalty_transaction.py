"""LoyaltyTransaction — ledger начислений/списаний баллов (PDD §5.2)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `loyalty_transactions` table — append-only
#            ledger of every loyalty points movement (accrual, redemption,
#            reservation, reversal, admin adjustment).
#   SCOPE:   Each row records a signed amount, the resulting balance_after,
#            optional order_id link, and a typed reason. Admin adjustments may
#            have order_id NULL; rows are never updated, only inserted.
#   DEPENDS: M-SHARED enums (LoyaltyTransactionType); SQLAlchemy 2.x ORM;
#            M-DATABASE Base; references users.id and orders.id.
#   LINKS:   PDD §5.2 (loyalty ledger), docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   LoyaltyTransaction - SQLAlchemy ORM class for `loyalty_transactions`
# END_MODULE_MAP

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import LoyaltyTransactionType
from shared.models import Base


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"
    __table_args__ = (
        sa.Index(
            "ix_loyalty_transactions_user_created_at",
            "user_id",
            sa.text("created_at DESC"),
        ),
    )

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
