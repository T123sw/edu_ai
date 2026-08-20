"""Add revisioned graph confirmation fields to knowledge builds.

Revision ID: 20260812_0015
Revises: 20260812_0014
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_0015"
down_revision: Union[str, None] = "20260812_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"] for column in inspector.get_columns("knowledge_builds")
    }

    if "revision" not in columns:
        op.add_column(
            "knowledge_builds",
            sa.Column(
                "revision",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            ),
        )
    if "graph_confirmed_at" not in columns:
        op.add_column(
            "knowledge_builds",
            sa.Column("graph_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "confirmed_graph_revision" not in columns:
        op.add_column(
            "knowledge_builds",
            sa.Column("confirmed_graph_revision", sa.Integer(), nullable=True),
        )
    if "confirmed_by" not in columns:
        op.add_column(
            "knowledge_builds",
            sa.Column("confirmed_by", sa.String(160), nullable=True),
        )

    indexes = {
        index["name"] for index in inspector.get_indexes("knowledge_builds")
    }
    index_name = "ix_knowledge_builds_confirmed_by"
    if index_name not in indexes:
        op.create_index(
            op.f(index_name),
            "knowledge_builds",
            ["confirmed_by"],
        )


def downgrade() -> None:
    # This reconciliation revision may only be stamping schema that was
    # already applied by the merged knowledge-build branch. Removing those
    # columns on downgrade would destroy valid application data.
    pass
