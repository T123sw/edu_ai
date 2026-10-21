"""Persist guided experiment sessions and idempotent operation batches."""
from alembic import op
import sqlalchemy as sa
revision='20261014_0040'
down_revision='20261014_0039'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('practice_sessions',sa.Column('id',sa.String(80),primary_key=True),sa.Column('owner',sa.String(160),nullable=False),sa.Column('practice_id',sa.String(200),nullable=False),sa.Column('artifact_revision',sa.String(64),nullable=False),sa.Column('seq',sa.Integer(),nullable=False),sa.Column('state',sa.JSON(),nullable=False),sa.Column('updated_at',sa.Float(),nullable=False))
    op.create_index('ix_practice_sessions_owner','practice_sessions',['owner'])
    op.create_table('practice_events',sa.Column('session_id',sa.String(80),sa.ForeignKey('practice_sessions.id'),primary_key=True),sa.Column('event_id',sa.String(80),primary_key=True),sa.Column('seq',sa.Integer(),nullable=False),sa.Column('batch_id',sa.String(80),nullable=False),sa.Column('request',sa.JSON(),nullable=False),sa.Column('response',sa.JSON(),nullable=False),sa.Column('created_at',sa.Float(),nullable=False),sa.UniqueConstraint('session_id','seq',name='uq_practice_event_seq'))
    op.create_index('ix_practice_events_batch_id','practice_events',['batch_id'])

    op.create_table('practice_journal_entries',sa.Column('session_id',sa.String(80),sa.ForeignKey('practice_sessions.id'),primary_key=True),sa.Column('entry_id',sa.String(80),primary_key=True),sa.Column('kind',sa.String(20),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_at',sa.Float(),nullable=False))

def downgrade():
    op.drop_table('practice_journal_entries')
    op.drop_table('practice_events')
    op.drop_table('practice_sessions')
