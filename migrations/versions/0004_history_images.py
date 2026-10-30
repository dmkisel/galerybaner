"""История хранит готовые картинки: путь к файлу и признак избранного.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("previews", sa.Column("image_key", sa.Text(), nullable=True))
    op.add_column(
        "previews",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Значение по умолчанию нужно было только для существующих строк.
    op.alter_column("previews", "is_favorite", server_default=None)


def downgrade() -> None:
    op.drop_column("previews", "is_favorite")
    op.drop_column("previews", "image_key")
