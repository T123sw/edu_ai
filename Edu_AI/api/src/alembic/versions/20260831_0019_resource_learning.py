"""Add versioned course resource learning evidence.

Revision ID: 20260831_0019
Revises: 20260831_0018
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260831_0019"
down_revision: Union[str, None] = "20260831_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resource_learning_manifests",
        sa.Column("manifest_id", sa.String(200), primary_key=True),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("resource_id", sa.String(240), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "course_id",
            "resource_id",
            "resource_version",
            name="uq_resource_learning_manifest_version",
        ),
    )
    op.create_index("ix_resource_learning_manifests_course_id", "resource_learning_manifests", ["course_id"])
    op.create_index("ix_resource_learning_manifests_resource_id", "resource_learning_manifests", ["resource_id"])

    op.create_table(
        "resource_learning_sessions",
        sa.Column("session_id", sa.String(200), primary_key=True),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("resource_id", sa.String(240), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("invalid_reason", sa.Text()),
    )
    op.create_index("ix_resource_learning_sessions_course_id", "resource_learning_sessions", ["course_id"])
    op.create_index("ix_resource_learning_sessions_resource_id", "resource_learning_sessions", ["resource_id"])
    op.create_index("ix_resource_learning_sessions_student_id", "resource_learning_sessions", ["student_id"])
    op.create_index(
        "ix_resource_learning_sessions_active_scope",
        "resource_learning_sessions",
        ["student_id", "course_id", "resource_id", "resource_version", "status"],
    )

    op.create_table(
        "resource_learning_events",
        sa.Column("event_id", sa.String(200), primary_key=True),
        sa.Column("session_id", sa.String(200), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("scene_id", sa.String(240), nullable=False),
        sa.Column("timeline_from_ms", sa.Integer()),
        sa.Column("timeline_to_ms", sa.Integer()),
        sa.Column("action_id", sa.String(240)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["resource_learning_sessions.session_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_resource_learning_events_session_sequence"),
    )
    op.create_index("ix_resource_learning_events_session_id", "resource_learning_events", ["session_id"])

    op.create_table(
        "resource_learning_coverage",
        sa.Column("student_id", sa.String(160), primary_key=True),
        sa.Column("course_id", sa.String(200), primary_key=True),
        sa.Column("resource_id", sa.String(240), primary_key=True),
        sa.Column("resource_version", sa.Integer(), primary_key=True),
        sa.Column("scene_id", sa.String(240), primary_key=True),
        sa.Column("covered_ranges_json", sa.JSON(), nullable=False),
        sa.Column("covered_duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "resource_question_attempts",
        sa.Column("question_attempt_id", sa.String(200), primary_key=True),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("resource_id", sa.String(240), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.String(240), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("answer_payload", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("knowledge_point_ids", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "student_id", "course_id", "resource_id", "resource_version", "question_id", "attempt_number",
            name="uq_resource_question_attempt_number",
        ),
        sa.UniqueConstraint(
            "student_id", "course_id", "resource_id", "resource_version", "idempotency_key", "question_id",
            name="uq_resource_question_attempt_idempotency",
        ),
    )
    op.create_index("ix_resource_question_attempts_student_id", "resource_question_attempts", ["student_id"])
    op.create_index("ix_resource_question_attempts_course_id", "resource_question_attempts", ["course_id"])
    op.create_index("ix_resource_question_attempts_resource_id", "resource_question_attempts", ["resource_id"])

    op.create_table(
        "resource_learning_progress",
        sa.Column("student_id", sa.String(160), primary_key=True),
        sa.Column("course_id", sa.String(200), primary_key=True),
        sa.Column("resource_id", sa.String(240), primary_key=True),
        sa.Column("resource_version", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("explanation_covered_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("explanation_total_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("explanation_coverage_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("required_question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answered_question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question_completion_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("correct_count_first", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count_latest", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("demo_view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("demo_interaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_activity_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "task_resource_evidence_refs",
        sa.Column("evidence_ref_id", sa.String(200), primary_key=True),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("resource_id", sa.String(240), nullable=False),
        sa.Column("resource_version", sa.Integer(), nullable=False),
        sa.Column("resource_progress_updated_at", sa.DateTime(timezone=True)),
        sa.Column("resource_completed_at", sa.DateTime(timezone=True)),
        sa.Column("condition_status", sa.String(32), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "task_id", "student_id", "resource_id", "resource_version",
            name="uq_task_resource_evidence_version",
        ),
    )
    op.create_index("ix_task_resource_evidence_refs_task_id", "task_resource_evidence_refs", ["task_id"])
    op.create_index("ix_task_resource_evidence_refs_student_id", "task_resource_evidence_refs", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_task_resource_evidence_refs_student_id", table_name="task_resource_evidence_refs")
    op.drop_index("ix_task_resource_evidence_refs_task_id", table_name="task_resource_evidence_refs")
    op.drop_table("task_resource_evidence_refs")
    op.drop_table("resource_learning_progress")
    op.drop_index("ix_resource_question_attempts_resource_id", table_name="resource_question_attempts")
    op.drop_index("ix_resource_question_attempts_course_id", table_name="resource_question_attempts")
    op.drop_index("ix_resource_question_attempts_student_id", table_name="resource_question_attempts")
    op.drop_table("resource_question_attempts")
    op.drop_table("resource_learning_coverage")
    op.drop_index("ix_resource_learning_events_session_id", table_name="resource_learning_events")
    op.drop_table("resource_learning_events")
    op.drop_index("ix_resource_learning_sessions_active_scope", table_name="resource_learning_sessions")
    op.drop_index("ix_resource_learning_sessions_student_id", table_name="resource_learning_sessions")
    op.drop_index("ix_resource_learning_sessions_resource_id", table_name="resource_learning_sessions")
    op.drop_index("ix_resource_learning_sessions_course_id", table_name="resource_learning_sessions")
    op.drop_table("resource_learning_sessions")
    op.drop_index("ix_resource_learning_manifests_resource_id", table_name="resource_learning_manifests")
    op.drop_index("ix_resource_learning_manifests_course_id", table_name="resource_learning_manifests")
    op.drop_table("resource_learning_manifests")

