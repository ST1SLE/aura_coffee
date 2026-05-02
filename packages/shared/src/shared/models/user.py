# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `users` table — the root identity record
#            for every customer account.
#   SCOPE:   Holds non-PII identity fields only (id, phone_hash, status,
#            timestamps); PII (raw phone, display name) lives in UserProfile
#            per INV-013. Status drives the user lifecycle state machine.
#   DEPENDS: M-SHARED enums (UserStatus); SQLAlchemy 2.x ORM; M-DATABASE Base.
#   LINKS:   PDD §5.2 (users table), PDD §6.4 (user lifecycle),
#            docs/development-plan.xml M-SHARED, INV-013.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   User - SQLAlchemy ORM class for the `users` table (no PII, INV-013)
# END_MODULE_MAP

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import UserStatus
from shared.models import Base

if TYPE_CHECKING:
    from shared.models.loyalty_account import LoyaltyAccount
    from shared.models.user_profile import UserProfile


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone_hash", name="users_phone_hash_key"),
        Index("ix_users_phone_hash", "phone_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    profile: Mapped["UserProfile"] = relationship(back_populates="user")
    loyalty_account: Mapped["LoyaltyAccount | None"] = relationship(
        back_populates="user"
    )
