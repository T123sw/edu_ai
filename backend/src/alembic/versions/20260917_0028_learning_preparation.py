"""Durable personal preparation delivery and notifications."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '20260917_0028'
down_revision = '20260917_0027'
branch_labels = None
depends_on = None

def upgrade():
    j=sa.JSON().with_variant(JSONB(),'postgresql')
    def s(n,size,pk=False): return sa.Column(n,sa.String(size),primary_key=pk,nullable=False)
    def i(n,pk=False): return sa.Column(n,sa.Integer(),primary_key=pk,nullable=False)
    def f(n): return sa.Column(n,sa.Float(),nullable=False)
    def p(n): return sa.Column(n,j,nullable=False)
    op.create_table('course_production_runs',sa.Column('preparation_id',sa.String(200),sa.ForeignKey('course_preparations.preparation_id'),primary_key=True),
        s('owner',160),s('course_id',200),s('topic_id',240),s('operation_id',200),s('token',40),f('lease_until'),f('deadline'),s('state',24),p('payload'),p('result'))
    op.create_table('course_personal_manifest_heads',s('owner',160,True),s('course_id',200,True),i('version'))
    op.create_table('course_personal_manifest_versions',s('owner',160,True),s('course_id',200,True),i('version',True),p('payload'))
    op.create_table('learning_preparation_notifications',s('event_id',200,True),s('preparation_id',200),s('owner',160),s('course_id',200),i('attempt_no'),i('revision'),p('payload'),f('read_at'))

def downgrade():
    for name in ('learning_preparation_notifications','course_personal_manifest_versions','course_personal_manifest_heads','course_production_runs'):
        op.drop_table(name)
