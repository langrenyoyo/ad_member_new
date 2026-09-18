"""Persist member payment recipient independently of verified real name."""
from alembic import op
import sqlalchemy as sa

revision = 'e914_member_receive_name'
down_revision = 'd913fe3c92b8'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('members',sa.Column('receive_name',sa.String(64),nullable=False,server_default=''))

def downgrade():
    op.drop_column('members','receive_name')
