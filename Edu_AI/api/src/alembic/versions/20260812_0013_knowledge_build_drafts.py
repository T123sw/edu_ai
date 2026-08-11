"""Add revisioned graph confirmation fields to knowledge builds.

Revision ID: 20260812_0013
Revises: 20260811_0012
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_0013"
down_revision: Union[str, None] = "20260811_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_builds",
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "knowledge_builds",
        sa.Column("graph_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_builds",
        sa.Column("confirmed_graph_revision", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_builds",
        sa.Column("confirmed_by", sa.String(160), nullable=True),
    )
    op.create_index(
        op.f("ix_knowledge_builds_confirmed_by"),
        "knowledge_builds",
        ["confirmed_by"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_knowledge_builds_confirmed_by"), table_name="knowledge_builds"
    )
    op.drop_column("knowledge_builds", "confirmed_by")
    op.drop_column("knowledge_builds", "confirmed_graph_revision")
    op.drop_column("knowledge_builds", "graph_confirmed_at")
    op.drop_column("knowledge_builds", "revision")
