"""Create versioned learning-task assessments.

Revision ID: 20260812_0013
Revises: 20260811_0012
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260812_0013"
down_revision: Union[str, None] = "20260811_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "assessments",
        sa.Column("assessment_id", sa.String(200), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_version_id", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"], ["learning_tasks.task_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint("task_id", name="uq_assessments_task_id"),
    )
    op.create_index("ix_assessments_course_id", "assessments", ["course_id"])
    op.create_index(
        "ix_assessments_current_version_id", "assessments", ["current_version_id"]
    )

    op.create_table(
        "assessment_versions",
        sa.Column("assessment_version_id", sa.String(200), nullable=False),
        sa.Column("assessment_id", sa.String(200), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_mode", sa.String(32), nullable=False),
        sa.Column("assessment_mode", sa.String(32), nullable=False),
        sa.Column("pass_threshold", sa.Float(), nullable=False),
        sa.Column("mastery_threshold", sa.Float(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("score_policy", sa.String(40), nullable=False),
        sa.Column("answer_reveal_policy", sa.String(64), nullable=False),
        sa.Column("shuffle_questions", sa.Boolean(), nullable=False),
        sa.Column("shuffle_options", sa.Boolean(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.assessment_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("assessment_version_id"),
        sa.UniqueConstraint(
            "assessment_id", "version_number", name="uq_assessment_versions_number"
        ),
    )
    op.create_index(
        "ix_assessment_versions_assessment_id", "assessment_versions", ["assessment_id"]
    )
    op.create_index("ix_assessment_versions_status", "assessment_versions", ["status"])

    op.create_table(
        "assessment_items",
        sa.Column("assessment_item_id", sa.String(200), nullable=False),
        sa.Column("assessment_version_id", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(64), nullable=False),
        sa.Column("prompt", jsonb, nullable=False),
        sa.Column("scoring_key", jsonb, nullable=False),
        sa.Column("rubric", jsonb, nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("grading_provider", sa.String(64), nullable=False),
        sa.Column("knowledge_point_ids", jsonb, nullable=False),
        sa.Column("source_refs", jsonb, nullable=False),
        sa.Column("source_exposure_state", sa.String(32), nullable=False),
        sa.Column("created_origin", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"],
            ["assessment_versions.assessment_version_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("assessment_item_id"),
        sa.UniqueConstraint(
            "assessment_version_id", "position", name="uq_assessment_items_position"
        ),
    )
    op.create_index(
        "ix_assessment_items_version_id", "assessment_items", ["assessment_version_id"]
    )

    op.create_table(
        "assessment_assignments",
        sa.Column("assessment_assignment_id", sa.String(200), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("assessment_version_id", sa.String(200), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("attempts_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_attempt_id", sa.String(200), nullable=True),
        sa.Column("best_final_score", sa.Float(), nullable=True),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("answers_revealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_version_id"], ["assessment_versions.assessment_version_id"]
        ),
        sa.PrimaryKeyConstraint("assessment_assignment_id"),
        sa.UniqueConstraint(
            "task_id",
            "student_id",
            "cycle_number",
            name="uq_assessment_assignment_cycle",
        ),
    )
    for column in ("task_id", "course_id", "student_id", "assessment_version_id"):
        op.create_index(
            f"ix_assessment_assignments_{column}", "assessment_assignments", [column]
        )

    op.create_table(
        "assessment_attempts",
        sa.Column("attempt_id", sa.String(200), nullable=False),
        sa.Column("assessment_assignment_id", sa.String(200), nullable=False),
        sa.Column("assessment_version_id", sa.String(200), nullable=False),
        sa.Column("task_id", sa.String(200), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("student_id", sa.String(160), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("result", sa.String(32), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_by", sa.String(160), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_assignment_id"],
            ["assessment_assignments.assessment_assignment_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "assessment_assignment_id",
            "attempt_number",
            name="uq_assessment_attempt_number",
        ),
    )
    for column in (
        "assessment_assignment_id",
        "assessment_version_id",
        "task_id",
        "course_id",
        "student_id",
        "status",
    ):
        op.create_index(f"ix_assessment_attempts_{column}", "assessment_attempts", [column])

    op.create_table(
        "assessment_answers",
        sa.Column("answer_id", sa.String(200), nullable=False),
        sa.Column("attempt_id", sa.String(200), nullable=False),
        sa.Column("assessment_item_id", sa.String(200), nullable=False),
        sa.Column("answer", jsonb, nullable=False),
        sa.Column("artifact_refs", jsonb, nullable=False),
        sa.Column("auto_score", sa.Float(), nullable=True),
        sa.Column("ai_suggestion", jsonb, nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["assessment_attempts.attempt_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_item_id"], ["assessment_items.assessment_item_id"]
        ),
        sa.PrimaryKeyConstraint("answer_id"),
        sa.UniqueConstraint(
            "attempt_id", "assessment_item_id", name="uq_assessment_answer_item"
        ),
    )
    op.create_index("ix_assessment_answers_attempt_id", "assessment_answers", ["attempt_id"])
    op.create_index(
        "ix_assessment_answers_item_id", "assessment_answers", ["assessment_item_id"]
    )

    op.create_table(
        "assessment_reviews",
        sa.Column("review_id", sa.String(200), nullable=False),
        sa.Column("attempt_id", sa.String(200), nullable=False),
        sa.Column("assessment_item_id", sa.String(200), nullable=True),
        sa.Column("reviewer_id", sa.String(160), nullable=False),
        sa.Column("previous_score", sa.Float(), nullable=True),
        sa.Column("new_score", sa.Float(), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("comment_private", sa.Text(), nullable=False),
        sa.Column("comment_student_visible", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["assessment_attempts.attempt_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_item_id"], ["assessment_items.assessment_item_id"]
        ),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index("ix_assessment_reviews_attempt_id", "assessment_reviews", ["attempt_id"])
    op.create_index(
        "ix_assessment_reviews_item_id", "assessment_reviews", ["assessment_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_assessment_reviews_item_id", table_name="assessment_reviews")
    op.drop_index("ix_assessment_reviews_attempt_id", table_name="assessment_reviews")
    op.drop_table("assessment_reviews")
    op.drop_index("ix_assessment_answers_item_id", table_name="assessment_answers")
    op.drop_index("ix_assessment_answers_attempt_id", table_name="assessment_answers")
    op.drop_table("assessment_answers")
    for column in reversed(
        (
            "assessment_assignment_id",
            "assessment_version_id",
            "task_id",
            "course_id",
            "student_id",
            "status",
        )
    ):
        op.drop_index(f"ix_assessment_attempts_{column}", table_name="assessment_attempts")
    op.drop_table("assessment_attempts")
    for column in reversed(("task_id", "course_id", "student_id", "assessment_version_id")):
        op.drop_index(f"ix_assessment_assignments_{column}", table_name="assessment_assignments")
    op.drop_table("assessment_assignments")
    op.drop_index("ix_assessment_items_version_id", table_name="assessment_items")
    op.drop_table("assessment_items")
    op.drop_index("ix_assessment_versions_status", table_name="assessment_versions")
    op.drop_index("ix_assessment_versions_assessment_id", table_name="assessment_versions")
    op.drop_table("assessment_versions")
    op.drop_index("ix_assessments_current_version_id", table_name="assessments")
    op.drop_index("ix_assessments_course_id", table_name="assessments")
    op.drop_table("assessments")
