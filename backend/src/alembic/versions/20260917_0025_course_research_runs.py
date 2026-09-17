"""Checkpointed course research/path stage jobs.

Revision ID: 20260917_0025
Revises: 20260917_0024
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260917_0025'
down_revision = '20260917_0024'
branch_labels = None
depends_on = None


def upgrade():
    payload = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.create_table('course_research_runs',
        sa.Column('run_id', sa.String(200), primary_key=True),
        sa.Column('owner_user_id', sa.String(160), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('request_sha256', sa.String(64), nullable=False),
        sa.Column('request_payload', payload, nullable=False),
        sa.Column('config_snapshot', payload, nullable=False),
        sa.Column('state_payload', payload, nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('recoveries', sa.Integer(), nullable=False),
        sa.Column('lease_token', sa.String(64)),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('error_code', sa.String(80)),
        sa.UniqueConstraint('owner_user_id', 'request_id', name='uq_course_research_request'),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'canceled')", name='research_status'),
        sa.CheckConstraint('revision >= 1 AND recoveries >= 0', name='research_revision'))
    op.create_index('ix_course_research_claim', 'course_research_runs', ['status', 'lease_until'])


def downgrade():
    op.drop_table('course_research_runs')
