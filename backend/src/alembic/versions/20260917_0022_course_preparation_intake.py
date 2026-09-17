"""Atomic course preparation intake, first attempt and ordered events.

Revision ID: 20260917_0022
Revises: 20260910_0021
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260917_0022'
down_revision = '20260910_0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    payload_type = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.create_table(
        'course_preparations',
        sa.Column('preparation_id', sa.String(200), primary_key=True),
        sa.Column('owner_user_id', sa.String(160), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('request_sha256', sa.String(64), nullable=False),
        sa.Column('operation', sa.String(32), nullable=False),
        sa.Column('request_payload', payload_type, nullable=False),
        sa.Column('current_attempt_no', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('owner_user_id', 'request_id', name='uq_course_preparation_request'),
        sa.CheckConstraint('current_attempt_no >= 1 AND revision >= 1', name='positive_revision'),
        sa.CheckConstraint("operation IN ('create_course', 'supplement_node', 'revise_resource', 'adjust_course')",
                           name='valid_operation'),
    )
    op.create_table(
        'course_preparation_attempts',
        sa.Column('preparation_id', sa.String(200),
                  sa.ForeignKey('course_preparations.preparation_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('attempt_no', sa.Integer(), primary_key=True),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('stage', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('attempt_no >= 1', name='positive_attempt'),
        sa.CheckConstraint("status IN ('accepted', 'running', 'checking', 'succeeded', 'failed', 'canceled')",
                           name='valid_status'),
        sa.CheckConstraint("stage IN ('normalize', 'ingest', 'research_scope', 'plan', 'research_nodes', "
                           "'produce', 'review', 'repair', 'commit')", name='valid_stage'),
    )
    op.create_table(
        'course_preparation_events',
        sa.Column('event_id', sa.String(200), primary_key=True),
        sa.Column('preparation_id', sa.String(200), nullable=False),
        sa.Column('attempt_no', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('payload', payload_type, nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('preparation_id', 'sequence', name='uq_course_preparation_event_sequence'),
        sa.ForeignKeyConstraint(['preparation_id', 'attempt_no'],
                                ['course_preparation_attempts.preparation_id', 'course_preparation_attempts.attempt_no'],
                                ondelete='CASCADE'),
        sa.CheckConstraint('sequence >= 1 AND revision >= 1', name='positive_sequence'),
        sa.CheckConstraint("event_type IN ('accepted', 'stage_changed', 'child_updated', 'check_finished', "
                           "'cancel_requested', 'succeeded', 'failed', 'canceled')", name='valid_event_type'),
    )


def downgrade() -> None:
    op.drop_table('course_preparation_events')
    op.drop_table('course_preparation_attempts')
    op.drop_table('course_preparations')
