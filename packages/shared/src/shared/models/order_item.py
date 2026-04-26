"""OrderItem — неизменяемые снимки позиций заказа (PDD §5.2, INV-014, §7.7).

menu_item_id и size_option_id хранятся как ссылки (не FK) для Repeat Order
Chain: архивирование меню не должно ломать историю заказов.
"""

# START_MODULE_CONTRACT
#   PURPOSE: ORM declaration of the `order_items` table — immutable per-line
#            snapshot of a sold item taken at checkout time.
#   SCOPE:   Stores fully denormalized data (menu_item name in ru/en, unit
#            price, size label, modifiers_snapshot JSONB, quantity, line_total)
#            so that historic orders survive menu archiving (PDD §7.7 Repeat
#            Order Chain). menu_item_id and size_option_id are deliberately
#            plain integers — NOT foreign keys — to prevent referential
#            cascades from rewriting history. Rows are insert-only (INV-014).
#   DEPENDS: SQLAlchemy 2.x ORM; M-DATABASE Base; references orders.id only.
#   LINKS:   PDD §5.2 (order_items table), PDD §7.7 (Repeat Order Chain),
#            INV-014 (order_items immutability), docs/development-plan.xml M-SHARED.
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   OrderItem - SQLAlchemy ORM class for `order_items` (immutable, INV-014)
# END_MODULE_MAP

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    # INV-014 + §7.7: ссылка, а НЕ FK — при архивировании меню история уцелеет
    menu_item_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    menu_item_name_ru: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    menu_item_name_en: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    size_option_id: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    size_label: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    unit_price: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    # Снимок модификаторов на момент оформления заказа (INV-014)
    modifiers_snapshot: Mapped[list] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    line_total: Mapped[int] = mapped_column(sa.Integer(), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")  # noqa: F821
