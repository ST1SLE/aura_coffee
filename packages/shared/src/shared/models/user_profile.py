# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `user_profiles` table — PII-isolated
#            companion row to User (encrypted phone, display name, language).
#   SCOPE:   Stores the encrypted phone bytes and other PII attributes 1:1 with
#            User; deliberately separated so non-PII queries on `users` never
#            pull personal data into result sets.
#   DEPENDS: SQLAlchemy 2.x ORM; M-DATABASE Base; references users.id.
#   LINKS:   PDD §5.2 (user_profiles table), INV-013 (PII isolation),
#            docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserProfile - SQLAlchemy ORM class for `user_profiles` (PII-bearing, INV-013)
# END_MODULE_MAP

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models import Base

if TYPE_CHECKING:
    from shared.models.user import User


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    phone: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str] = mapped_column(
        String(2), nullable=False, default="ru"
    )

    user: Mapped["User"] = relationship(back_populates="profile")
