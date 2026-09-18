"""Add independent subsidy recipient fields."""
from alembic import op
import sqlalchemy as sa

revision = 'd912a8e63c52'
down_revision = 'c912f7d52b41'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ['receive_name', 'receive_tel']:
        op.add_column('subsidies', sa.Column(name, sa.String(64), nullable=False, server_default=''))


def downgrade() -> None:
    for name in ['receive_tel', 'receive_name']:
        op.drop_column('subsidies', name)
