"""Persist understanding checks, source-bound summaries and non-chat notifications."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260917_0032'
down_revision='20260917_0031'
branch_labels=None
depends_on=None


def upgrade():
    payload=sa.JSON().with_variant(postgresql.JSONB(),'postgresql')
    op.create_table('learning_checks',sa.Column('check_id',sa.String(80),primary_key=True),
        sa.Column('owner',sa.String(160),nullable=False),sa.Column('session_id',sa.String(200),sa.ForeignKey('learning_topic_sessions.session_id'),nullable=False),
        sa.Column('course_id',sa.String(200),nullable=False),sa.Column('topic_id',sa.String(240),nullable=False),
        sa.Column('source_ref',payload,nullable=False),sa.Column('content_digest',sa.String(64),nullable=False),sa.Column('item',payload,nullable=False),sa.Column('created_at',sa.Float(),nullable=False))
    op.create_table('learning_check_attempts',sa.Column('owner',sa.String(160),primary_key=True),sa.Column('request_id',sa.String(36),primary_key=True),
        sa.Column('check_id',sa.String(80),sa.ForeignKey('learning_checks.check_id'),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),
        sa.Column('answer',payload,nullable=False),sa.Column('result',payload,nullable=False),sa.Column('created_at',sa.Float(),nullable=False))
    op.create_table('learning_summaries',sa.Column('owner',sa.String(160),primary_key=True),
        sa.Column('session_id',sa.String(200),sa.ForeignKey('learning_topic_sessions.session_id'),primary_key=True),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('source_revision',sa.Integer(),nullable=False),sa.Column('memory_epoch',sa.Integer(),nullable=False),
        sa.Column('source_ids',payload,nullable=False),sa.Column('content',sa.Text(),nullable=False))
    op.create_table('learning_notifications',sa.Column('event_id',sa.String(160),primary_key=True),sa.Column('owner',sa.String(160),nullable=False),
        sa.Column('course_id',sa.String(200),nullable=False),sa.Column('payload',payload,nullable=False),sa.Column('read_at',sa.Float()),sa.Column('created_at',sa.Float(),nullable=False))


def downgrade():
    for table in ('learning_notifications','learning_summaries','learning_check_attempts','learning_checks'): op.drop_table(table)
