# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `staff_accounts` table — internal logins
#            for admins, baristas, and couriers.
#   SCOPE:   Distinct from User (which is for customers). Stores login,
#            password_hash, role enum, display_name, is_active flag, and
#            timestamps. Couriers in this table are referenced by
#            DeliveryAssignment.courier_id.
#   DEPENDS: M-SHARED enums (StaffRole); SQLAlchemy 2.x ORM; M-DATABASE Base.
#   LINKS:   PDD §5.2 (staff_accounts table),
#            docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   StaffAccount - SQLAlchemy ORM class for `staff_accounts`
# END_MODULE_MAP

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import StaffRole
from shared.models import Base


class StaffAccount(Base):
    __tablename__ = "staff_accounts"
    __table_args__ = (
        UniqueConstraint("login", name="staff_accounts_login_key"),
        Index("ix_staff_accounts_login", "login"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    login: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    role: Mapped[StaffRole] = mapped_column(
        Enum(
            StaffRole,
            name="staff_role",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )
