"""PromocodeUsage — фиксация использования промокода в заказе (PDD §5.2)."""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `promocode_usages` table — append-only
#            record that promocode P was applied by user U on order O.
#   SCOPE:   Three required FKs (promocode_id, user_id, order_id) all with
#            ondelete=RESTRICT so historic redemptions cannot be silently
#            erased. Used by service-layer validators to enforce per-user
#            and global use caps on Promocode.
#   DEPENDS: SQLAlchemy 2.x ORM; M-DATABASE Base; references promocodes.id,
#            users.id, orders.id.
#   LINKS:   PDD §5.2 (promocode_usages table),
#            docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PromocodeUsage - SQLAlchemy ORM class for `promocode_usages`
# END_MODULE_MAP

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.models import Base


class PromocodeUsage(Base):
    __tablename__ = "promocode_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    promocode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("promocodes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
