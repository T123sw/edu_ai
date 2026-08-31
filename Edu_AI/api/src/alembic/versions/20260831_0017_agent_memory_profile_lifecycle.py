"""Allow repeated profile invalidation and recreation.

Revision ID: 20260831_0017
Revises: 20260831_0016
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260831_0017"
down_revision: Union[str, None] = "20260831_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = {
        item["name"] for item in inspector.get_unique_constraints("user_profile_facts")
    }
    name = "uq_user_profile_facts_active_axis"
    if name in constraints:
        op.drop_constraint(name, "user_profile_facts", type_="unique")


def downgrade() -> None:
    # Restoring this constraint can fail after valid repeated lifecycle events.
    pass
