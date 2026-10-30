"""Модели SQLAlchemy 2.0.

Схема соответствует docs/spec.md. Имена ограничений заданы явно, чтобы
autogenerate в Alembic не давал ложных диффов.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


banner_tags = Table(
    "banner_tags",
    Base.metadata,
    Column("banner_id", BigInteger, ForeignKey("banners.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Banner(Base):
    """Шаблон: баннер (Ordinary/Popup), Push или СМС."""

    __tablename__ = "banners"
    __table_args__ = (
        Index(
            "uq_banners_url",
            "url",
            unique=True,
            postgresql_where=text("url IS NOT NULL AND url <> ''"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # ordinary | popup | push | sms
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="ordinary")

    # Картинка есть только у Ordinary и Popup.
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Текст кнопки — нужен Popup-баннерам.
    action_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Цвет центра баннера: hex для показа, оттенок для сортировки по спектру.
    center_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    center_hue: Mapped[float | None] = mapped_column(
        Numeric(6, 2, asdecimal=False), nullable=True
    )

    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tags: Mapped[list[Tag]] = relationship(
        secondary=banner_tags,
        back_populates="banners",
        order_by="Tag.name",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover - отладочное
        return f"Banner(id={self.id!r}, url={self.url!r})"


class Tag(Base):
    """Тег. `name` сохраняет регистр для отображения, `name_key` — для поиска."""

    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name_key", name="uq_tags_name_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    banners: Mapped[list[Banner]] = relationship(
        secondary=banner_tags, back_populates="tags"
    )


class Preview(Base):
    """История: сохранённый макет «тема + сообщение». Хранит параметры, не картинку."""

    __tablename__ = "previews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    banner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("banners.id", ondelete="SET NULL"), nullable=True
    )

    theme_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Тип шаблона: ordinary | popup | push | sms
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="ordinary")

    theme_scale: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    message_scale: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    theme_pos_x: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    theme_pos_y: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    message_pos_x: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    message_pos_y: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)

    max_width: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    stroke_width: Mapped[float] = mapped_column(
        Numeric(5, 4, asdecimal=False), nullable=False, default=0.0
    )
    align: Mapped[str] = mapped_column(Text, nullable=False, default="left")
    color: Mapped[str] = mapped_column(Text, nullable=False, default="#FFFFFF")

    # Готовый рендер лежит файлом в data/history, здесь — его ключ.
    image_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    banner: Mapped[Banner | None] = relationship(lazy="selectin")


text_template_tags = Table(
    "text_template_tags",
    Base.metadata,
    Column(
        "template_id",
        BigInteger,
        ForeignKey("text_templates.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class TextTemplate(Base):
    """Текстовый шаблон из Блокнота: тема и сообщение, без картинки."""

    __tablename__ = "text_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # ordinary | popup | push | sms — к какому каналу относится текст
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="ordinary")

    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_banner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("banners.id", ondelete="SET NULL"), nullable=True
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tags: Mapped[list[Tag]] = relationship(
        secondary=text_template_tags, order_by="Tag.name", lazy="selectin"
    )

    @property
    def length(self) -> int:
        return len(self.title.strip()) + len(self.message.strip())


class ShowcaseEntry(Base):
    """Строка витрины из CRM: один баннер в одном месте одной комбинации.

    Таблицу наполняет внешний процесс; приложение её только читает.
    Комбинация собирается по `combination_key` — все её строки имеют один
    и тот же `clients_count`.
    """

    __tablename__ = "communication_showcase"
    __table_args__ = (
        UniqueConstraint("combination_key", "slot", name="uq_showcase_combo_slot"),
        Index("ix_showcase_page", "page"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    combination_key: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[str] = mapped_column(Text, nullable=False)
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    banner_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    clients_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
