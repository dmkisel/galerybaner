"""Витрина читается из таблицы, которую наполняет CRM.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27

Вместо внутренних `combinations`/`placements` — плоская `communication_showcase`:
одна строка = один баннер в одном посадочном месте одной комбинации.
Существующие данные переносятся со ссылками из галереи.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "communication_showcase",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("combination_key", sa.Text(), nullable=False),
        sa.Column("page", sa.Text(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("banner_url", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("clients_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("combination_key", "slot", name="uq_showcase_combo_slot"),
    )
    op.create_index("ix_showcase_page", "communication_showcase", ["page"])

    # Серверные значения нужны были только для создания таблицы.
    for column in ("banner_url", "text", "clients_count"):
        op.alter_column("communication_showcase", column, server_default=None)

    op.execute(
        """
        INSERT INTO communication_showcase
            (combination_key, page, slot, banner_url, text, clients_count)
        SELECT 'combo-' || c.id, c.page, p.slot, COALESCE(b.url, ''), p.text, c.clients_count
        FROM combinations c
        JOIN placements p ON p.combination_id = c.id
        LEFT JOIN banners b ON b.id = p.banner_id
        """
    )

    op.drop_table("placements")
    op.drop_table("combinations")


def downgrade() -> None:
    op.create_table(
        "combinations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("page", sa.Text(), nullable=False),
        sa.Column("clients_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "placements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("combination_id", sa.BigInteger(), nullable=False),
        sa.Column("slot", sa.Text(), nullable=False),
        sa.Column("banner_id", sa.BigInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["combination_id"], ["combinations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["banner_id"], ["banners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("combination_id", "slot", name="uq_placements_combination_slot"),
    )
    op.execute(
        """
        INSERT INTO combinations (page, clients_count)
        SELECT DISTINCT ON (combination_key) page, clients_count
        FROM communication_showcase
        ORDER BY combination_key
        """
    )
    op.execute(
        """
        INSERT INTO placements (combination_id, slot, banner_id, text)
        SELECT c.id, s.slot, b.id, s.text
        FROM communication_showcase s
        JOIN combinations c ON c.page = s.page AND c.clients_count = s.clients_count
        LEFT JOIN banners b ON b.url = s.banner_url
        """
    )
    op.drop_index("ix_showcase_page", table_name="communication_showcase")
    op.drop_table("communication_showcase")
