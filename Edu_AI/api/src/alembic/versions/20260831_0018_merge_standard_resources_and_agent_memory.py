"""Merge standard-resource and Agent Memory migration heads.

Revision ID: 20260831_0018
Revises: 20260824_0017, 20260831_0017
Create Date: 2026-08-31
"""

from typing import Sequence, Union


revision: str = "20260831_0018"
down_revision: Union[str, tuple[str, str], None] = (
    "20260824_0017",
    "20260831_0017",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
