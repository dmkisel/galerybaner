"""Два текстовых блока в истории превью: тема + сообщение.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27

Одиночный текст из 0001 переезжает в «тему»: история сохраняется, колонки
старого формата удаляются.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

NEW_SCALE_COLUMNS = (
    "theme_scale",
    "message_scale",
    "theme_pos_x",
    "theme_pos_y",
    "message_pos_x",
    "message_pos_y",
)


def upgrade() -> None:
    op.add_column(
        "previews",
        sa.Column("theme_text", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "previews",
        sa.Column("message_text", sa.Text(), nullable=False, server_default=sa.text("''")),
    )

    for name in NEW_SCALE_COLUMNS:
        op.add_column("previews", sa.Column(name, sa.Numeric(precision=5, scale=4), nullable=True))

    # Старый одиночный текст становится темой; сообщение подстраиваем мельче.
    op.execute(
        """
        UPDATE previews SET
            theme_text = text,
            theme_scale = text_scale,
            theme_pos_x = pos_x,
            theme_pos_y = pos_y,
            message_scale = GREATEST(text_scale * 0.6, 0.01),
            message_pos_x = pos_x,
            message_pos_y = 1 - pos_y
        """
    )
    op.execute(
        """
        UPDATE previews SET
            theme_scale = COALESCE(theme_scale, 0.155),
            message_scale = COALESCE(message_scale, 0.090),
            theme_pos_x = COALESCE(theme_pos_x, 0.40),
            theme_pos_y = COALESCE(theme_pos_y, 0.30),
            message_pos_x = COALESCE(message_pos_x, 0.40),
            message_pos_y = COALESCE(message_pos_y, 0.70)
        """
    )

    for name in NEW_SCALE_COLUMNS:
        op.alter_column("previews", name, nullable=False)

    # Серверные значения по умолчанию были нужны только на время backfill.
    op.alter_column("previews", "theme_text", server_default=None)
    op.alter_column("previews", "message_text", server_default=None)

    op.drop_column("previews", "text")
    op.drop_column("previews", "text_scale")
    op.drop_column("previews", "pos_x")
    op.drop_column("previews", "pos_y")


def downgrade() -> None:
    op.add_column("previews", sa.Column("text", sa.Text(), nullable=True))
    op.add_column("previews", sa.Column("text_scale", sa.Numeric(precision=5, scale=4), nullable=True))
    op.add_column("previews", sa.Column("pos_x", sa.Numeric(precision=5, scale=4), nullable=True))
    op.add_column("previews", sa.Column("pos_y", sa.Numeric(precision=5, scale=4), nullable=True))

    op.execute(
        """
        UPDATE previews SET
            text = theme_text,
            text_scale = theme_scale,
            pos_x = theme_pos_x,
            pos_y = theme_pos_y
        """
    )

    for name in ("text", "text_scale", "pos_x", "pos_y"):
        op.alter_column("previews", name, nullable=False)

    for name in NEW_SCALE_COLUMNS:
        op.drop_column("previews", name)
    op.drop_column("previews", "message_text")
    op.drop_column("previews", "theme_text")
