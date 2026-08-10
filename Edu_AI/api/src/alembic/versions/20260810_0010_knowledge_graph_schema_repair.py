"""Repair knowledge graph columns missing from an already-stamped database.

Revision ID: 20260810_0010
Revises: 20260810_0009
Create Date: 2026-08-10

Some local databases were stamped at 0009 before that revision gained the
knowledge graph provenance columns.  Alembic will not rerun an amended
revision, so this follow-up reconciles the physical schema without touching
the existing graph payloads.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260810_0010"
down_revision: Union[str, None] = "20260810_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "knowledge_graph_versions"
SOURCE_BUILD_INDEX = "ix_knowledge_graph_versions_source_build_id"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}

    if "source_build_id" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("source_build_id", sa.String(200), nullable=True),
        )
    if "published_at" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        )

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if SOURCE_BUILD_INDEX not in indexes:
        op.create_index(
            op.f(SOURCE_BUILD_INDEX),
            TABLE_NAME,
            ["source_build_id"],
        )


def downgrade() -> None:
    # 0009's intended schema already contains these columns.  Removing them
    # here would corrupt healthy databases and discard provenance metadata.
    pass
