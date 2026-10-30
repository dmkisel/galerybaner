"""Комбинации баннеров: несколько вариантов на одну страницу.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27

Прежние посадочные места (одна страница = один набор) переезжают в комбинации:
на каждую страницу создаётся один вариант, число клиентов переходит на его уровень.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.alter_column("combinations", "clients_count", server_default=None)

    op.add_column("placements", sa.Column("combination_id", sa.BigInteger(), nullable=True))

    # Один вариант на страницу из текущих раскладок; клиентов берём по минимуму мест.
    op.execute(
        """
        INSERT INTO combinations (page, clients_count)
        SELECT page, MIN(clients_count) FROM placements GROUP BY page
        """
    )
    op.execute(
        """
        UPDATE placements p SET combination_id = c.id
        FROM combinations c WHERE c.page = p.page
        """
    )

    op.drop_constraint("uq_placements_page_slot", "placements", type_="unique")
    op.alter_column("placements", "combination_id", nullable=False)
    op.create_foreign_key(
        "fk_placements_combination",
        "placements",
        "combinations",
        ["combination_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_placements_combination_slot", "placements", ["combination_id", "slot"]
    )
    op.drop_column("placements", "page")
    op.drop_column("placements", "clients_count")


def downgrade() -> None:
    op.add_column(
        "placements",
        sa.Column("page", sa.Text(), nullable=True),
    )
    op.add_column(
        "placements",
        sa.Column("clients_count", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE placements p SET page = c.page, clients_count = c.clients_count
        FROM combinations c WHERE c.id = p.combination_id
        """
    )
    op.alter_column("placements", "page", nullable=False)
    op.alter_column("placements", "clients_count", nullable=False)

    op.drop_constraint("uq_placements_combination_slot", "placements", type_="unique")
    op.drop_constraint("fk_placements_combination", "placements", type_="foreignkey")
    op.drop_column("placements", "combination_id")
    op.create_unique_constraint("uq_placements_page_slot", "placements", ["page", "slot"])
    op.drop_table("combinations")
