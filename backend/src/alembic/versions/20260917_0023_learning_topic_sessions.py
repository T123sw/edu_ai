"""Persistent learning topic sessions and append-only turn identities.

Revision ID: 20260917_0023
Revises: 20260917_0022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260917_0023'
down_revision = '20260917_0022'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('learning_topic_sessions',
        sa.Column('session_id', sa.String(200), sa.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('owner', sa.String(160), nullable=False),
        sa.Column('course_id', sa.String(200), nullable=False),
        sa.Column('topic_id', sa.String(240), nullable=False),
        sa.Column('next_position', sa.Integer(), nullable=False),
        sa.Column('import_metadata', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.UniqueConstraint('owner', 'course_id', 'topic_id', name='uq_learning_topic_owner'),
        sa.CheckConstraint('next_position >= 0', name='learning_position_nonnegative'))
    op.create_table('learning_agent_turns',
        sa.Column('session_id', sa.String(200), sa.ForeignKey('learning_topic_sessions.session_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('request_id', sa.String(200), primary_key=True),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('lease_until', sa.Float(), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('resource_id', sa.String(240), nullable=False),
        sa.Column('answer', sa.Text()),
        sa.Column('error', sa.String(80)),
        sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name='learning_turn_status'))


def downgrade():
    op.drop_table('learning_agent_turns')
    op.drop_table('learning_topic_sessions')
