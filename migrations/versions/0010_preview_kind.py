"""Тип шаблона в истории: popup, push и СМС тоже сохраняются.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-28

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "previews",
        sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'ordinary'")),
    )
    op.alter_column("previews", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("previews", "kind")
