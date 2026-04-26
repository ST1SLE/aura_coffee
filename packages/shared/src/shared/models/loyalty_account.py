# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `loyalty_accounts` table — per-user
#            current loyalty points balance (one row per user).
#   SCOPE:   Snapshot balance only; the authoritative history lives in
#            LoyaltyTransaction. Mutations to `balance` must be paired with a
#            LoyaltyTransaction insert in the same DB transaction.
#   DEPENDS: SQLAlchemy 2.x ORM; M-DATABASE Base; references users.id.
#   LINKS:   PDD §5.2 (loyalty_accounts table), docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   LoyaltyAccount - SQLAlchemy ORM class for `loyalty_accounts`
# END_MODULE_MAP

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models import Base


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="loyalty_account")
