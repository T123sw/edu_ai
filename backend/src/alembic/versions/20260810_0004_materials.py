"""Create generated material, version, and artifact reference tables.

Revision ID: 20260810_0004
Revises: 20260810_0003
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0004"
down_revision: Union[str, None] = "20260810_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "materials",
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("material_type", sa.String(80), nullable=False),
        sa.Column("material_id", sa.String(240), nullable=False),
        sa.Column("title", sa.String(500), server_default="", nullable=False),
        sa.Column("status", sa.String(64), server_default="ready", nullable=False),
        sa.Column("visibility", sa.String(32), server_default="course", nullable=False),
        sa.Column("owner_user_id", sa.String(160), nullable=True),
        sa.Column("scope_type", sa.String(64), server_default="course", nullable=False),
        sa.Column("scope_id", sa.String(240), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("source_job_id", sa.String(200), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("course_id", "material_type", "material_id", name=op.f("pk_materials")),
    )
    for column in ("owner_user_id", "scope_id", "source_job_id", "content_hash"):
        op.create_index(op.f(f"ix_materials_{column}"), "materials", [column])
    op.create_table(
        "material_versions",
        sa.Column("material_version_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("material_type", sa.String(80), nullable=False),
        sa.Column("material_id", sa.String(240), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id", "material_type", "material_id"],
            ["materials.course_id", "materials.material_type", "materials.material_id"],
            name="fk_material_versions_material", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("material_version_id", name=op.f("pk_material_versions")),
        sa.UniqueConstraint("course_id", "material_type", "material_id", "version", name="uq_material_versions_version"),
    )
    op.create_index(op.f("ix_material_versions_course_id"), "material_versions", ["course_id"])
    op.create_table(
        "artifact_files",
        sa.Column("artifact_file_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.String(200), nullable=False),
        sa.Column("material_type", sa.String(80), nullable=False),
        sa.Column("material_id", sa.String(240), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("metadata_payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id", "material_type", "material_id"],
            ["materials.course_id", "materials.material_type", "materials.material_id"],
            name="fk_artifact_files_material", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artifact_file_id", name=op.f("pk_artifact_files")),
        sa.UniqueConstraint("course_id", "material_type", "material_id", "path", name="uq_artifact_files_path"),
    )
    op.create_index(op.f("ix_artifact_files_course_id"), "artifact_files", ["course_id"])
    op.create_table(
        "migration_quarantine",
        sa.Column("quarantine_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("quarantine_id", name=op.f("pk_migration_quarantine")),
        sa.UniqueConstraint("domain", "source_path", name="uq_migration_quarantine_source"),
    )
    op.create_index(op.f("ix_migration_quarantine_domain"), "migration_quarantine", ["domain"])


def downgrade() -> None:
    op.drop_index(op.f("ix_migration_quarantine_domain"), table_name="migration_quarantine")
    op.drop_table("migration_quarantine")
    op.drop_index(op.f("ix_artifact_files_course_id"), table_name="artifact_files")
    op.drop_table("artifact_files")
    op.drop_index(op.f("ix_material_versions_course_id"), table_name="material_versions")
    op.drop_table("material_versions")
    for column in reversed(("owner_user_id", "scope_id", "source_job_id", "content_hash")):
        op.drop_index(op.f(f"ix_materials_{column}"), table_name="materials")
    op.drop_table("materials")
