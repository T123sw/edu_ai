"""Persist assessment submission idempotency keys.

Revision ID: 20260812_0014
Revises: 20260812_0013
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_0014"
down_revision: Union[str, None] = "20260812_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assessment_attempts",
        sa.Column("submission_idempotency_key", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessment_attempts", "submission_idempotency_key")
