"""Global TAKU publisher and rotating eCPM keys."""
from alembic import op
import sqlalchemy as sa

revision = 'e934_taku_global_keys'
down_revision = 'e933_reward_ledger_coin_log'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('taku_global_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('publisher_key', sa.String(512), nullable=False),
        sa.Column('server_ecpm_key', sa.Text(), nullable=False),
        sa.Column('client_ecpm_key', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('taku_global_configs')
