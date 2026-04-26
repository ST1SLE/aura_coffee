"""ShopSettings — singleton-таблица с настройками магазина (PDD §5.2)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `shop_settings` table — singleton row
#            (CHECK id = 1) holding shop-wide configuration: location,
#            delivery economics, loyalty percent, prep/auto-close timers,
#            working_hours JSONB.
#   SCOPE:   Exactly one row at id=1 (enforced by ck_shop_settings_singleton).
#            Read by core-api during pricing and delivery quoting; written
#            only by admin endpoints. No PII.
#   DEPENDS: SQLAlchemy 2.x ORM; M-DATABASE Base.
#   LINKS:   PDD §5.2 (shop_settings table),
#            docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ShopSettings - SQLAlchemy ORM class for `shop_settings` (singleton, id=1)
# END_MODULE_MAP

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
    auto_close_minutes: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        default=60,
        server_default=sa.text("60"),
    )
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
