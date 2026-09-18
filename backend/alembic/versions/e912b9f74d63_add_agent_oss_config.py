"""Independent agent OSS configuration."""
from alembic import op
import sqlalchemy as sa
revision='e912b9f74d63'
down_revision='d912a8e63c52'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('agents',sa.Column('oss_config',sa.Text(),nullable=False,server_default='{}'))
def downgrade():
    op.drop_column('agents','oss_config')
