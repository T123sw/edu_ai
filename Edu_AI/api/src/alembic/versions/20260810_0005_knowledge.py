"""Create knowledge library and runtime index tables.

Revision ID: 20260810_0005
Revises: 20260810_0004
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0005"
down_revision: Union[str, None] = "20260810_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "knowledge_libraries",
        sa.Column("library_id", sa.String(240), nullable=False),
        sa.Column("library_type", sa.String(64), nullable=False),
        sa.Column("course_id", sa.String(200), nullable=True),
        sa.Column("owner_user_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata_payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("library_id", name=op.f("pk_knowledge_libraries")),
    )
    for column in ("library_type", "course_id", "owner_user_id"):
        op.create_index(op.f(f"ix_knowledge_libraries_{column}"), "knowledge_libraries", [column])
    op.create_table(
        "knowledge_documents",
        sa.Column("library_id", sa.String(240), nullable=False),
        sa.Column("document_id", sa.String(260), nullable=False),
        sa.Column("filename", sa.String(500), server_default="", nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("scope_type", sa.String(64), server_default="course", nullable=False),
        sa.Column("scope_id", sa.String(240), nullable=True),
        sa.Column("status", sa.String(64), server_default="ready", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["library_id"], ["knowledge_libraries.library_id"], name=op.f("fk_knowledge_documents_library_id_knowledge_libraries"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("library_id", "document_id", name=op.f("pk_knowledge_documents")),
    )
    op.create_index(op.f("ix_knowledge_documents_content_hash"), "knowledge_documents", ["content_hash"])
    op.create_index(op.f("ix_knowledge_documents_scope_id"), "knowledge_documents", ["scope_id"])
    op.create_table(
        "knowledge_graph_versions",
        sa.Column("graph_version_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("library_id", sa.String(240), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("graph_payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["library_id"], ["knowledge_libraries.library_id"], name=op.f("fk_knowledge_graph_versions_library_id_knowledge_libraries"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("graph_version_id", name=op.f("pk_knowledge_graph_versions")),
        sa.UniqueConstraint("library_id", "version", name="uq_knowledge_graph_versions_version"),
    )
    op.create_index(op.f("ix_knowledge_graph_versions_library_id"), "knowledge_graph_versions", ["library_id"])
    op.create_table(
        "runtime_index_entries",
        sa.Column("index_name", sa.String(80), nullable=False),
        sa.Column("entry_key", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.String(160), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("index_name", "entry_key", name=op.f("pk_runtime_index_entries")),
    )
    op.create_index(op.f("ix_runtime_index_entries_owner_user_id"), "runtime_index_entries", ["owner_user_id"])
    op.create_index(op.f("ix_runtime_index_entries_content_hash"), "runtime_index_entries", ["content_hash"])


def downgrade() -> None:
    op.drop_index(op.f("ix_runtime_index_entries_content_hash"), table_name="runtime_index_entries")
    op.drop_index(op.f("ix_runtime_index_entries_owner_user_id"), table_name="runtime_index_entries")
    op.drop_table("runtime_index_entries")
    op.drop_index(op.f("ix_knowledge_graph_versions_library_id"), table_name="knowledge_graph_versions")
    op.drop_table("knowledge_graph_versions")
    op.drop_index(op.f("ix_knowledge_documents_scope_id"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_content_hash"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    for column in reversed(("library_type", "course_id", "owner_user_id")):
        op.drop_index(op.f(f"ix_knowledge_libraries_{column}"), table_name="knowledge_libraries")
    op.drop_table("knowledge_libraries")
