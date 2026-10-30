"""Блокнот: текстовые шаблоны живут отдельно от картинок.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-29

Существующие push/смс переносятся в новую таблицу, из баннеров удаляются.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "text_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("message", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("source_banner_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_banner_id"], ["banners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("title", "message"):
        op.alter_column("text_templates", column, server_default=None)

    op.create_table(
        "text_template_tags",
        sa.Column("template_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["text_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("template_id", "tag_id"),
    )

    op.execute(
        """
        INSERT INTO text_templates (title, message, source_banner_id)
        SELECT title, message, NULL FROM banners WHERE kind IN ('push', 'sms')
        """
    )
    op.execute(
        """
        INSERT INTO text_template_tags (template_id, tag_id)
        SELECT tt.id, bt.tag_id
        FROM banners b
        JOIN banner_tags bt ON bt.banner_id = b.id
        JOIN text_templates tt ON tt.title = b.title AND tt.message = b.message
        WHERE b.kind IN ('push', 'sms')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute("DELETE FROM banners WHERE kind IN ('push', 'sms')")


def downgrade() -> None:
    op.drop_table("text_template_tags")
    op.drop_table("text_templates")
