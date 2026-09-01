"""Create job ledger and event tables.

Revision ID: 20260810_0003
Revises: 20260810_0002
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0003"
down_revision: Union[str, None] = "20260810_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "jobs",
        sa.Column("edu_job_id", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("step", sa.String(length=160), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("owner_user_id", sa.String(length=160), nullable=False),
        sa.Column("course_id", sa.String(length=200), nullable=True),
        sa.Column("scope_type", sa.String(length=64), server_default="course", nullable=False),
        sa.Column("scope_id", sa.String(length=240), nullable=True),
        sa.Column("retry_of_job_id", sa.String(length=200), nullable=True),
        sa.Column("parent_job_id", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("edu_job_id", name=op.f("pk_jobs")),
    )
    for column in (
        "kind", "status", "owner_user_id", "course_id", "scope_id",
        "retry_of_job_id", "parent_job_id",
    ):
        op.create_index(op.f(f"ix_jobs_{column}"), "jobs", [column])
    op.create_table(
        "job_events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("edu_job_id", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("step", sa.String(length=160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(
            ["edu_job_id"], ["jobs.edu_job_id"],
            name=op.f("fk_job_events_edu_job_id_jobs"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_job_events")),
        sa.UniqueConstraint("edu_job_id", "version", name="uq_job_events_version"),
    )
    op.create_index(op.f("ix_job_events_edu_job_id"), "job_events", ["edu_job_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_job_events_edu_job_id"), table_name="job_events")
    op.drop_table("job_events")
    for column in reversed((
        "kind", "status", "owner_user_id", "course_id", "scope_id",
        "retry_of_job_id", "parent_job_id",
    )):
        op.drop_index(op.f(f"ix_jobs_{column}"), table_name="jobs")
    op.drop_table("jobs")
