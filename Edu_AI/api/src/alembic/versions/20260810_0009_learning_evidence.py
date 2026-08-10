"""Add durable learning evidence and completion projection fields.

Revision ID: 20260810_0009
Revises: 20260810_0008
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0009"
down_revision: Union[str, None] = "20260810_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_events",
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "learning_progress",
        sa.Column(
            "completion_basis",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
    )
    op.add_column(
        "learning_progress",
        sa.Column(
            "evidence_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "learning_progress",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE learning_progress
        SET completion_basis='self_reported'
        WHERE status='completed' AND completion_basis='none'
        """
    )


def downgrade() -> None:
    op.drop_column("learning_progress", "last_activity_at")
    op.drop_column("learning_progress", "evidence_count")
    op.drop_column("learning_progress", "completion_basis")
    op.drop_column("learning_events", "evidence")
