"""Versioned learning facts, event receipts and transactional outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '20260917_0024'
down_revision = '20260917_0023'
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), 'postgresql')
    def owner():
        return sa.Column('owner', sa.String(160), primary_key=True)
    def course():
        return sa.Column('course_id', sa.String(200), primary_key=True)
    def key():
        return sa.Column('resource_key', sa.String(64), primary_key=True)
    def event_id():
        return sa.Column('event_id', sa.String(36), primary_key=True)
    op.create_table('self_learning_fact_revisions', owner(), course(), sa.Column('revision', sa.Integer(), nullable=False))
    op.create_table('self_learning_events', owner(), event_id(),
        sa.Column('course_id', sa.String(200), nullable=False), sa.Column('topic_id', sa.String(240), nullable=False),
        sa.Column('payload_hash', sa.String(64), nullable=False), sa.Column('event', json_type, nullable=False), sa.Column('receipt', json_type, nullable=False))
    op.create_table('self_learning_resource_states', owner(), course(), key(),
        sa.Column('resource_ref', json_type, nullable=False), sa.Column('state', json_type, nullable=False), sa.Column('revision', sa.Integer(), nullable=False))
    op.create_table('self_learning_reading_streams', owner(), course(), key(),
        sa.Column('stream_id', sa.String(36), primary_key=True), sa.Column('sequence', sa.Integer(), nullable=False), sa.Column('locator', json_type, nullable=False))
    op.create_table('self_learning_topic_states', owner(), course(),
        sa.Column('topic_id', sa.String(240), primary_key=True), sa.Column('value', sa.String(24), nullable=False), sa.Column('revision', sa.Integer(), nullable=False))
    op.create_table('learning_progress_outbox', owner(), event_id(), sa.Column('payload', json_type, nullable=False))


def downgrade():
    for table in ('learning_progress_outbox', 'self_learning_topic_states', 'self_learning_reading_streams',
                  'self_learning_resource_states', 'self_learning_events', 'self_learning_fact_revisions'):
        op.drop_table(table)
