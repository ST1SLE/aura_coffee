"""ShopSettings — singleton-таблица с настройками магазина (PDD §5.2)."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.models import Base


class ShopSettings(Base):
    __tablename__ = "shop_settings"
    __table_args__ = (
        sa.CheckConstraint("id = 1", name="ck_shop_settings_singleton"),
    )

    # Singleton: всегда id=1 (CHECK гарантирует)
    id: Mapped[int] = mapped_column(sa.Integer(), primary_key=True, autoincrement=False)
    shop_lat: Mapped[float] = mapped_column(sa.Numeric(10, 7), nullable=False)
    shop_lon: Mapped[float] = mapped_column(sa.Numeric(10, 7), nullable=False)
    delivery_radius_km: Mapped[float] = mapped_column(sa.Numeric(6, 2), nullable=False)
    min_delivery_amount: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    free_delivery_threshold: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    delivery_fee: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    loyalty_percent: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    default_prep_time_minutes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    estimated_delivery_time_minutes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    working_hours: Mapped[dict] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.text("now()"),
    )
