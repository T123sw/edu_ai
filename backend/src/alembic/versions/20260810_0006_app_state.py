"""Create PostgreSQL-backed application state records.

Revision ID: 20260810_0006
Revises: 20260810_0005
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_0006"
down_revision: Union[str, None] = "20260810_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_state_records",
        sa.Column("namespace", sa.String(120), nullable=False),
        sa.Column("record_key", sa.String(300), nullable=False),
        sa.Column("owner_user_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("namespace", "record_key", name=op.f("pk_app_state_records")),
    )
    op.create_index(op.f("ix_app_state_records_owner_user_id"), "app_state_records", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_app_state_records_owner_user_id"), table_name="app_state_records")
    op.drop_table("app_state_records")
