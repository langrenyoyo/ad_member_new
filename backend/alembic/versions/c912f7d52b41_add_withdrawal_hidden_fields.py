"""Add source delivery fields and nullable member internal-account flag."""
from alembic import op
import sqlalchemy as sa

revision = 'c912f7d52b41'
down_revision = 'b912e6d41a30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('members', sa.Column('is_true', sa.Integer(), nullable=True))
    op.add_column('withdrawals', sa.Column('delivery_name', sa.String(128), nullable=False, server_default=''))
    op.add_column('withdrawals', sa.Column('delivery_no', sa.String(128), nullable=False, server_default=''))
    op.add_column('withdrawals', sa.Column('remark', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    for column in ['remark', 'delivery_no', 'delivery_name']:
        op.drop_column('withdrawals', column)
    op.drop_column('members', 'is_true')
