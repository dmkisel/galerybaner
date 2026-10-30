"""Избранное для баннеров и текстов.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-29

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("banners", "text_templates"):
        op.add_column(
            table,
            sa.Column(
                "is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
        )
        op.alter_column(table, "is_favorite", server_default=None)


def downgrade() -> None:
    for table in ("text_templates", "banners"):
        op.drop_column(table, "is_favorite")
