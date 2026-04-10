"""ORM-модели меню: Category, MenuItem, SizeOption, Modifier, menu_item_modifiers."""

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.enums import CategoryType, SizeLabel
from shared.models import Base

# M:N junction table — объект Table, не mapped-класс
menu_item_modifiers = sa.Table(
    "menu_item_modifiers",
    Base.metadata,
    sa.Column(
        "menu_item_id",
        sa.BigInteger(),
        sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "modifier_id",
        sa.BigInteger(),
        sa.ForeignKey("modifiers.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.PrimaryKeyConstraint("menu_item_id", "modifier_id", name="pk_menu_item_modifiers"),
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True)
    type: Mapped[CategoryType] = mapped_column(
        sa.Enum(CategoryType, name="category_type", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    name_ru: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    is_visible: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text("now()"), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text("now()"), default=lambda: datetime.now(UTC)
    )

    menu_items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} type={self.type}>"


class Modifier(Base):
    __tablename__ = "modifiers"

    id: Mapped[int] = mapped_column(sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True)
    name_ru: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    price: Mapped[int] = mapped_column(
        sa.Integer(),
        sa.CheckConstraint("price >= 0", name="ck_modifiers_price_non_negative"),
        nullable=False,
        default=0,
    )
    available: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)

    menu_items: Mapped[list["MenuItem"]] = relationship(
        secondary=menu_item_modifiers,
        back_populates="modifiers",
    )

    def __repr__(self) -> str:
        return f"<Modifier id={self.id} name_ru={self.name_ru!r}>"


class SizeOption(Base):
    __tablename__ = "size_options"

    id: Mapped[int] = mapped_column(sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True)
    menu_item_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[SizeLabel] = mapped_column(
        sa.Enum(SizeLabel, name="size_label", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    price: Mapped[int] = mapped_column(
        sa.Integer(),
        sa.CheckConstraint("price >= 0", name="ck_size_options_price_non_negative"),
        nullable=False,
        default=0,
    )
    available: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="size_options")

    def __repr__(self) -> str:
        return f"<SizeOption id={self.id} label={self.label} price={self.price}>"


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger(),
        sa.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name_ru: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    name_en: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    description_ru: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    description_en: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    base_price: Mapped[int] = mapped_column(
        sa.Integer(),
        sa.CheckConstraint("base_price >= 0", name="ck_menu_items_base_price_non_negative"),
        nullable=False,
        default=0,
    )
    image_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    available: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    archived: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text("now()"), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text("now()"), default=lambda: datetime.now(UTC)
    )

    category: Mapped["Category"] = relationship(back_populates="menu_items")
    size_options: Mapped[list["SizeOption"]] = relationship(
        back_populates="menu_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    modifiers: Mapped[list["Modifier"]] = relationship(
        secondary=menu_item_modifiers,
        back_populates="menu_items",
    )

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} name_ru={self.name_ru!r}>"
