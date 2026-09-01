"""Create learning task, event, and progress tables.

Revision ID: 20260810_0007
Revises: 20260810_0006
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0007"
down_revision: Union[str, None] = "20260810_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "learning_tasks",
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("resource_refs", jsonb, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("knowledge_point_ids", jsonb, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(160), nullable=True),
        sa.PrimaryKeyConstraint("task_id", name=op.f("pk_learning_tasks")),
    )
    op.create_index(op.f("ix_learning_tasks_course_id"), "learning_tasks", ["course_id"])
    op.create_index(op.f("ix_learning_tasks_status"), "learning_tasks", ["status"])
    op.create_table(
        "learning_events",
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("resource_ref", jsonb, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["learning_tasks.task_id"], name=op.f("fk_learning_events_task_id_learning_tasks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_learning_events")),
    )
    for column in ("course_id", "task_id", "student_id"):
        op.create_index(op.f(f"ix_learning_events_{column}"), "learning_events", [column])
    op.create_table(
        "learning_progress",
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["learning_tasks.task_id"], name=op.f("fk_learning_progress_task_id_learning_tasks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "student_id", name=op.f("pk_learning_progress")),
    )
    op.create_index(op.f("ix_learning_progress_course_id"), "learning_progress", ["course_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_progress_course_id"), table_name="learning_progress")
    op.drop_table("learning_progress")
    for column in reversed(("course_id", "task_id", "student_id")):
        op.drop_index(op.f(f"ix_learning_events_{column}"), table_name="learning_events")
    op.drop_table("learning_events")
    op.drop_index(op.f("ix_learning_tasks_status"), table_name="learning_tasks")
    op.drop_index(op.f("ix_learning_tasks_course_id"), table_name="learning_tasks")
    op.drop_table("learning_tasks")
