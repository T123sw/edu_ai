"""Separate published course snapshots from private learning revisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260917_0035'
down_revision='20260917_0034'
branch_labels=None
depends_on=None

def upgrade():
    payload=sa.JSON().with_variant(postgresql.JSONB(),'postgresql')
    op.create_table('published_preparation_manifests',sa.Column('course_id',sa.String(200),sa.ForeignKey('courses.course_id',ondelete='CASCADE'),primary_key=True),sa.Column('version',sa.Integer(),primary_key=True),
        sa.Column('source_owner_user_id',sa.String(160),sa.ForeignKey('users.user_id'),nullable=False),sa.Column('source_digest',sa.String(64),nullable=False),sa.Column('payload',payload,nullable=False),sa.Column('content_digest',sa.String(64),nullable=False),sa.Column('created_at',sa.Float(),nullable=False))
    op.create_table('published_preparation_pointers',sa.Column('course_id',sa.String(200),sa.ForeignKey('courses.course_id',ondelete='CASCADE'),primary_key=True),sa.Column('version',sa.Integer(),nullable=False))

def downgrade():
    op.drop_table('published_preparation_pointers');op.drop_table('published_preparation_manifests')
