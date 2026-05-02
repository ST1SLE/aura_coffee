"""Notification — уведомления пользователю (PDD §5.2)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `notifications` table — log of every
#            in-app or SMS notification dispatched to a user.
#   SCOPE:   Holds bilingual message bodies, channel/type/status, and
#            optional order_id linkage (OTP and system notifications may have
#            order_id NULL). Status drives the per-row dispatch lifecycle
#            (pending → sent | failed).
#   DEPENDS: M-SHARED enums (NotificationChannel, NotificationType,
#            NotificationStatus); SQLAlchemy 2.x ORM; M-DATABASE Base;
#            references users.id and orders.id.
#   LINKS:   PDD §5.2 (notifications table), docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Notification - SQLAlchemy ORM class for `notifications`
# END_MODULE_MAP

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.enums import NotificationChannel, NotificationStatus, NotificationType
from shared.models import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        sa.Index(
            "ix_notifications_user_created_at",
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
    # OTP и системные уведомления могут быть не привязаны к заказу
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        sa.Enum(
            NotificationChannel,
            name="notification_channel",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        sa.Enum(
            NotificationType,
            name="notification_type",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    message_ru: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    message_en: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        sa.Enum(
            NotificationStatus,
            name="notification_status",
            native_enum=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
