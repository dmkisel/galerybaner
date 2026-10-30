"""Переменные переходят на двойные фигурные скобки: {name} → {{name}}.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-30

"""

from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

COLUMNS = (
    ("text_templates", "title"),
    ("text_templates", "message"),
    ("banners", "title"),
    ("banners", "message"),
    ("previews", "theme_text"),
    ("previews", "message_text"),
    ("communication_showcase", "text"),
)

COLLAPSE = r"\{\{([^{}]+)\}\}"
WRAP = r"\{([^{}]+)\}"


def _update(table: str, column: str, pattern: str, replacement: str) -> str:
    return (
        f"UPDATE {table} SET {column} = "
        f"regexp_replace({column}, '{pattern}', '{replacement}', 'g') "
        f"WHERE position('{{' in {column}) > 0"
    )


def upgrade() -> None:
    for table, column in COLUMNS:
        # сначала схлопываем возможные двойные скобки до одинарных
        op.execute(_update(table, column, COLLAPSE, r"\1"))
        # затем оборачиваем одинарные в двойные
        op.execute(_update(table, column, WRAP, r"{{\1}}"))


def downgrade() -> None:
    for table, column in COLUMNS:
        op.execute(_update(table, column, COLLAPSE, r"\1"))
