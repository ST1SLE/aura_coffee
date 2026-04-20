import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.models import Base


class DeliveryAddress(Base):
    __tablename__ = "delivery_addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    address_text: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    lat: Mapped[float] = mapped_column(sa.Float, nullable=False)
    lon: Mapped[float] = mapped_column(sa.Float, nullable=False)
    apartment: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    entrance: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    floor: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    comment: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false"), default=False
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

    __table_args__ = (
        sa.Index("ix_delivery_addresses_user_id", "user_id"),
        sa.Index(
            "ix_delivery_addresses_user_default",
            "user_id",
            unique=True,
            postgresql_where=sa.text("is_default = true"),
            sqlite_where=sa.text("is_default = 1"),
        ),
    )
