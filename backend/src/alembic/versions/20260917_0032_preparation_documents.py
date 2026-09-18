"""Hash-bound versions of owner-authorized preparation uploads."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='20260917_0032'
down_revision='20260917_0031'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('preparation_document_versions',
        sa.Column('owner_user_id',sa.String(160),sa.ForeignKey('users.user_id'),primary_key=True),
        sa.Column('document_id',sa.String(200),primary_key=True),sa.Column('version',sa.Integer(),primary_key=True),
        sa.Column('content_sha256',sa.String(64),nullable=False),sa.Column('filename',sa.String(500),nullable=False),
        sa.Column('parsed',sa.JSON().with_variant(postgresql.JSONB(),'postgresql')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))

def downgrade(): op.drop_table('preparation_document_versions')
