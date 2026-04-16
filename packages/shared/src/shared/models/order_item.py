"""OrderItem — неизменяемые снимки позиций заказа (PDD §5.2, INV-014, §7.7).

menu_item_id и size_option_id хранятся как ссылки (не FK) для Repeat Order
Chain: архивирование меню не должно ломать историю заказов.
"""

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
