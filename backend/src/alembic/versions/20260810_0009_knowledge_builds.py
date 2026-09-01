"""Add governed course knowledge build records.

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
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column("knowledge_graph_versions", sa.Column("source_build_id", sa.String(200), nullable=True))
    op.add_column("knowledge_graph_versions", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_knowledge_graph_versions_source_build_id"), "knowledge_graph_versions", ["source_build_id"])
    op.create_table(
        "knowledge_builds",
        sa.Column("build_id", sa.String(200), nullable=False),
        sa.Column("library_id", sa.String(240), nullable=False),
        sa.Column("triggered_by", sa.String(160), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(80), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(300), nullable=True),
        sa.Column("plan_snapshot", jsonb, nullable=False),
        sa.Column("metrics", jsonb, nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("error", jsonb, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["library_id"], ["knowledge_libraries.library_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("build_id", name=op.f("pk_knowledge_builds")),
        sa.UniqueConstraint("library_id", "idempotency_key", name="uq_knowledge_builds_idempotency"),
    )
    op.create_index(op.f("ix_knowledge_builds_library_id"), "knowledge_builds", ["library_id"])
    op.create_index(op.f("ix_knowledge_builds_triggered_by"), "knowledge_builds", ["triggered_by"])
    op.create_index(op.f("ix_knowledge_builds_status"), "knowledge_builds", ["status"])

    op.create_table(
        "knowledge_source_candidates",
        sa.Column("candidate_id", sa.String(200), nullable=False),
        sa.Column("build_id", sa.String(200), nullable=False),
        sa.Column("topic_id", sa.String(200), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(700), nullable=False),
        sa.Column("domain", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("authority_tier", sa.String(80), nullable=True),
        sa.Column("license_info", jsonb, nullable=False),
        sa.Column("review_status", sa.String(40), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("metadata_payload", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["knowledge_builds.build_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("candidate_id", name=op.f("pk_knowledge_source_candidates")),
        sa.UniqueConstraint("build_id", "url", name="uq_knowledge_source_candidates_url"),
    )
    for column in ("build_id", "topic_id", "domain", "review_status"):
        op.create_index(op.f(f"ix_knowledge_source_candidates_{column}"), "knowledge_source_candidates", [column])

    op.create_table(
        "knowledge_quality_checks",
        sa.Column("check_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("build_id", sa.String(200), nullable=False),
        sa.Column("check_type", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("details", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["knowledge_builds.build_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("check_id", name=op.f("pk_knowledge_quality_checks")),
    )
    op.create_index(op.f("ix_knowledge_quality_checks_build_id"), "knowledge_quality_checks", ["build_id"])
    op.create_index(op.f("ix_knowledge_quality_checks_status"), "knowledge_quality_checks", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_quality_checks_status"), table_name="knowledge_quality_checks")
    op.drop_index(op.f("ix_knowledge_quality_checks_build_id"), table_name="knowledge_quality_checks")
    op.drop_table("knowledge_quality_checks")
    for column in reversed(("build_id", "topic_id", "domain", "review_status")):
        op.drop_index(op.f(f"ix_knowledge_source_candidates_{column}"), table_name="knowledge_source_candidates")
    op.drop_table("knowledge_source_candidates")
    op.drop_index(op.f("ix_knowledge_builds_status"), table_name="knowledge_builds")
    op.drop_index(op.f("ix_knowledge_builds_triggered_by"), table_name="knowledge_builds")
    op.drop_index(op.f("ix_knowledge_builds_library_id"), table_name="knowledge_builds")
    op.drop_table("knowledge_builds")
    op.drop_index(op.f("ix_knowledge_graph_versions_source_build_id"), table_name="knowledge_graph_versions")
    op.drop_column("knowledge_graph_versions", "published_at")
    op.drop_column("knowledge_graph_versions", "source_build_id")
