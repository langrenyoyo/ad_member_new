"""Keep unknown historical risk network status nullable."""
from alembic import op
import sqlalchemy as sa
revision = 'c913fd2b81a7'
down_revision = 'b913ec1a7096'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('risk_records', sa.Column('network_status', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('risk_records', 'network_status')
