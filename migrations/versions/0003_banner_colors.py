"""Цвет баннеров и уникальность ссылок.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("banners", sa.Column("center_color", sa.Text(), nullable=True))
    op.add_column(
        "banners", sa.Column("center_hue", sa.Numeric(precision=6, scale=2), nullable=True)
    )
    op.create_unique_constraint("uq_banners_url", "banners", ["url"])


def downgrade() -> None:
    op.drop_constraint("uq_banners_url", "banners", type_="unique")
    op.drop_column("banners", "center_hue")
    op.drop_column("banners", "center_color")
