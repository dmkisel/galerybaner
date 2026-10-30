"""Типы шаблонов: баннеры, push и СМС.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-28

* `kind` — ordinary | popup | push | sms;
* `title` и `message` — тема и текст шаблона;
* картинка нужна только баннерам, поэтому `url` становится необязательным,
  а уникальность переносится в частичный индекс (пустые ссылки не конфликтуют).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "banners",
        sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'ordinary'")),
    )
    op.add_column(
        "banners",
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "banners",
        sa.Column("message", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    for column in ("kind", "title", "message"):
        op.alter_column("banners", column, server_default=None)

    op.alter_column("banners", "url", existing_type=sa.Text(), nullable=True)

    op.drop_constraint("uq_banners_url", "banners", type_="unique")
    op.create_index(
        "uq_banners_url",
        "banners",
        ["url"],
        unique=True,
        postgresql_where=sa.text("url IS NOT NULL AND url <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_banners_url", table_name="banners")
    op.create_unique_constraint("uq_banners_url", "banners", ["url"])
    op.alter_column("banners", "url", existing_type=sa.Text(), nullable=False)
    for column in ("message", "title", "kind"):
        op.drop_column("banners", column)
