"""Тип коммуникации у текстовых шаблонов Блокнота.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-29

Существующие записи пришли из push/смс: у них есть тема → push, без темы → смс.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "text_templates",
        sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'ordinary'")),
    )
    op.execute(
        """
        UPDATE text_templates
        SET kind = CASE WHEN trim(title) <> '' THEN 'push' ELSE 'sms' END
        """
    )
    op.alter_column("text_templates", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("text_templates", "kind")
