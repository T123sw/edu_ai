"""Add Agent Memory V2 persistence tables.

Revision ID: 20260831_0016
Revises: 20260812_0015
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260831_0016"
down_revision: Union[str, None] = "20260812_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    json_type = _json_type()
    op.create_table(
        "conversation_episodes",
        sa.Column("episode_id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(200), nullable=False),
        sa.Column("owner_user_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200)),
        sa.Column(
            "message_start_position", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "message_end_position", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("salient_points", json_type, nullable=False),
        sa.Column("extractor", sa.String(120), nullable=False),
        sa.Column("extractor_version", sa.String(120), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("visibility", sa.String(64), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("conversation_id", "owner_user_id", "course_id"):
        op.create_index(
            f"ix_conversation_episodes_{column}", "conversation_episodes", [column]
        )
    op.create_index(
        "ix_conversation_episodes_owner_course",
        "conversation_episodes",
        ["owner_user_id", "course_id"],
    )

    op.create_table(
        "agent_memory_items",
        sa.Column("memory_id", sa.String(64), primary_key=True),
        sa.Column("subject_user_id", sa.String(160), nullable=False),
        sa.Column("owner_user_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200)),
        sa.Column("conversation_id", sa.String(200)),
        sa.Column("task_id", sa.String(200)),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("fact_kind", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_payload", json_type, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("visibility", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(240), nullable=False),
        sa.Column("source_span", sa.Text(), nullable=False),
        sa.Column("profile_axis", sa.String(80)),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("embedding", json_type),
        sa.Column("embedding_model", sa.String(200)),
        sa.Column("extractor", sa.String(120), nullable=False),
        sa.Column("extractor_version", sa.String(120), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fingerprint", name="uq_agent_memory_items_fingerprint"),
    )
    for column in (
        "subject_user_id",
        "owner_user_id",
        "course_id",
        "conversation_id",
        "task_id",
        "memory_type",
        "status",
        "profile_axis",
    ):
        op.create_index(
            f"ix_agent_memory_items_{column}", "agent_memory_items", [column]
        )
    op.create_index(
        "ix_agent_memory_items_recall_scope",
        "agent_memory_items",
        ["subject_user_id", "course_id", "status", "visibility"],
    )

    op.create_table(
        "user_profile_facts",
        sa.Column("profile_fact_id", sa.String(64), primary_key=True),
        sa.Column("subject_user_id", sa.String(160), nullable=False),
        sa.Column("course_id", sa.String(200)),
        sa.Column("course_scope_key", sa.String(200), nullable=False),
        sa.Column("profile_axis", sa.String(80), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("source_memory_ids", json_type, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("visibility", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "subject_user_id",
            "course_scope_key",
            "profile_axis",
            "status",
            name="uq_user_profile_facts_active_axis",
        ),
    )
    op.create_index(
        "ix_user_profile_facts_subject_user_id",
        "user_profile_facts",
        ["subject_user_id"],
    )
    op.create_index(
        "ix_user_profile_facts_course_id", "user_profile_facts", ["course_id"]
    )
    op.create_index(
        "ix_user_profile_facts_scope",
        "user_profile_facts",
        ["subject_user_id", "course_id", "status"],
    )

    op.create_table(
        "agent_memory_audit_events",
        sa.Column("audit_id", sa.String(64), primary_key=True),
        sa.Column("subject_user_id", sa.String(160), nullable=False),
        sa.Column("conversation_id", sa.String(200)),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("decision", sa.String(80), nullable=False),
        sa.Column("reason", sa.String(160), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("subject_user_id", "conversation_id", "event_type"):
        op.create_index(
            f"ix_agent_memory_audit_events_{column}",
            "agent_memory_audit_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("agent_memory_audit_events")
    op.drop_table("user_profile_facts")
    op.drop_table("agent_memory_items")
    op.drop_table("conversation_episodes")
