"""Create conversation and message tables.

Revision ID: 20260810_0002
Revises: 20260810_0001
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0002"
down_revision: Union[str, None] = "20260810_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.String(length=200), nullable=False),
        sa.Column("owner", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=500), server_default="", nullable=False),
        sa.Column("course_id", sa.String(length=200), nullable=True),
        sa.Column("scope_type", sa.String(length=64), server_default="course", nullable=False),
        sa.Column("scope_id", sa.String(length=240), nullable=True),
        sa.Column("state", _jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_payload", _jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("conversation_id", name=op.f("pk_conversations")),
    )
    op.create_index(op.f("ix_conversations_owner"), "conversations", ["owner"])
    op.create_index(op.f("ix_conversations_course_id"), "conversations", ["course_id"])
    op.create_index(op.f("ix_conversations_scope_id"), "conversations", ["scope_id"])
    op.create_table(
        "conversation_messages",
        sa.Column("message_id", sa.String(length=260), nullable=False),
        sa.Column("conversation_id", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("message_kind", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", _jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("position >= 0", name=op.f("ck_conversation_messages_non_negative_position")),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.conversation_id"],
            name=op.f("fk_conversation_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", name=op.f("pk_conversation_messages")),
        sa.UniqueConstraint("conversation_id", "position", name="uq_conversation_messages_position"),
    )
    op.create_index(
        op.f("ix_conversation_messages_conversation_id"),
        "conversation_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_messages_conversation_id"), table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index(op.f("ix_conversations_scope_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_course_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_owner"), table_name="conversations")
    op.drop_table("conversations")
