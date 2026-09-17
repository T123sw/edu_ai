"""Learning check snapshots, evidence, memory invalidation and derived summaries."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '20260917_0027'
down_revision = '20260917_0026'
branch_labels = None
depends_on = None


def upgrade():
    j = sa.JSON().with_variant(JSONB(), 'postgresql')
    def s(name, size, pk=False):
        return sa.Column(name, sa.String(size), primary_key=pk, nullable=False)
    def i(name): return sa.Column(name, sa.Integer(), nullable=False)
    def payload(name): return sa.Column(name, j, nullable=False)
    op.create_table('learning_checks', s('check_id',80,True), s('owner',160), s('course_id',200), s('topic_id',240),
        s('request_id',200), s('payload_hash',64), payload('question'), payload('source'), payload('objective_ids'),
        sa.Column('created_at',sa.Float(),nullable=False), sa.UniqueConstraint('owner','request_id',name='uq_learning_check_request'))
    op.create_table('learning_check_attempts', s('attempt_id',80,True), s('owner',160),
        sa.Column('check_id',sa.String(80),sa.ForeignKey('learning_checks.check_id'),nullable=False), s('request_id',36),
        s('payload_hash',64), payload('payload'), sa.Column('created_at',sa.Float(),nullable=False),
        sa.UniqueConstraint('owner','request_id',name='uq_learning_check_attempt_request'))
    op.create_table('learning_memory_epochs', s('owner',160,True), i('epoch'))
    op.create_table('learning_memory_suppressions', s('owner',160,True), s('source_id',240,True), s('field',80,True), i('epoch'))
    op.create_table('learning_memory_dependencies', s('owner',160,True), s('source_id',240,True), s('target_id',240,True), s('kind',40))
    op.create_table('learning_context_summaries',
        sa.Column('session_id',sa.String(200),sa.ForeignKey('learning_topic_sessions.session_id'),primary_key=True),
        s('owner',160),s('course_id',200),s('topic_id',240),i('revision'),i('covered_until'),i('memory_epoch'),i('facts_revision'),s('status',24),payload('payload'))
    op.create_table('learning_enrichment_receipts',s('owner',160,True),s('operation_id',200,True),s('payload_hash',64),payload('result'))
    op.create_table('learning_observations',s('turn_id',80,True),s('owner',160),s('course_id',200),s('topic_id',240),payload('payload'),s('status',24))
    op.create_table('learning_memory_outbox',s('owner',160,True),s('operation_id',200,True),payload('payload'))


def downgrade():
    for name in ('learning_memory_outbox','learning_observations','learning_enrichment_receipts','learning_context_summaries','learning_memory_dependencies',
                 'learning_memory_suppressions','learning_memory_epochs','learning_check_attempts','learning_checks'):
        op.drop_table(name)
