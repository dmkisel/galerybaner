"""Текст кнопки для Popup-баннеров.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-28

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "banners",
        sa.Column("action_text", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.alter_column("banners", "action_text", server_default=None)


def downgrade() -> None:
    op.drop_column("banners", "action_text")
