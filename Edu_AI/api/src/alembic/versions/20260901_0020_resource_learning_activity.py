"""Add explicit resource learning activity evidence.

Revision ID: 20260901_0020
Revises: 20260831_0019
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260901_0020"
down_revision: Union[str, None] = "20260831_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resource_learning_progress",
        sa.Column("completion_basis", sa.String(64)),
    )
    op.create_table(
        "resource_learning_activity_events",
        sa.Column("event_id", sa.String(200), primary_key=True),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("resource_id", sa.String(240), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_resource_learning_activity_events_student_id",
        "resource_learning_activity_events",
        ["student_id"],
    )
    op.create_index(
        "ix_resource_learning_activity_events_course_id",
        "resource_learning_activity_events",
        ["course_id"],
    )
    op.create_index(
        "ix_resource_learning_activity_events_resource_id",
        "resource_learning_activity_events",
        ["resource_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resource_learning_activity_events_resource_id",
        table_name="resource_learning_activity_events",
    )
    op.drop_index(
        "ix_resource_learning_activity_events_course_id",
        table_name="resource_learning_activity_events",
    )
    op.drop_index(
        "ix_resource_learning_activity_events_student_id",
        table_name="resource_learning_activity_events",
    )
    op.drop_table("resource_learning_activity_events")
    op.drop_column("resource_learning_progress", "completion_basis")
