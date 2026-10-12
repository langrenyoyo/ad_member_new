"""Link reward ledgers to the exact wallet journal entry."""
from alembic import op
import sqlalchemy as sa

revision = 'e933_reward_ledger_coin_log'
down_revision = 'e932_wallet_decimal'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('member_reward_ledgers', sa.Column('coin_log_id', sa.Integer(), nullable=True))
    op.create_index('ix_member_reward_ledgers_coin_log_id', 'member_reward_ledgers', ['coin_log_id'], unique=False)

def downgrade():
    op.drop_index('ix_member_reward_ledgers_coin_log_id', table_name='member_reward_ledgers')
    op.drop_column('member_reward_ledgers', 'coin_log_id')
