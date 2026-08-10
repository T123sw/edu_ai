"""Create PostgreSQL-backed durable task queue.

Revision ID: 20260810_0008
Revises: 20260810_0007
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0008"
down_revision: Union[str, None] = "20260810_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "durable_tasks",
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("workflow_type", sa.String(160), nullable=False),
        sa.Column("handler_version", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=True),
        sa.Column("scope_type", sa.String(64), nullable=False),
        sa.Column("scope_id", sa.String(240), nullable=True),
        sa.Column("command", jsonb, nullable=True),
        sa.Column("config_snapshot_id", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(300), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.Float(), nullable=False),
        sa.Column("lease_owner", sa.String(200), nullable=True),
        sa.Column("lease_expires_at", sa.Float(), nullable=True),
        sa.Column("heartbeat_at", sa.Float(), nullable=True),
        sa.Column("deadline_at", sa.Float(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("progress", jsonb, nullable=True),
        sa.Column("result", jsonb, nullable=True),
        sa.Column("result_ref", jsonb, nullable=True),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(80), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=True),
        sa.Column("finished_at", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("task_id", name=op.f("pk_durable_tasks")),
        sa.UniqueConstraint(
            "owner_user_id", "workflow_type", "idempotency_key",
            name="uq_durable_tasks_idempotency",
        ),
    )
    for column in (
        "owner_user_id", "course_id", "scope_id", "status", "available_at",
        "lease_expires_at", "deadline_at", "updated_at",
    ):
        op.create_index(op.f(f"ix_durable_tasks_{column}"), "durable_tasks", [column])


def downgrade() -> None:
    for column in reversed((
        "owner_user_id", "course_id", "scope_id", "status", "available_at",
        "lease_expires_at", "deadline_at", "updated_at",
    )):
        op.drop_index(op.f(f"ix_durable_tasks_{column}"), table_name="durable_tasks")
    op.drop_table("durable_tasks")
