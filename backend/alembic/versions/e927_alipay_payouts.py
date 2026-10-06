"""Alipay account binding and durable withdrawal orders."""
from alembic import op
import sqlalchemy as sa

revision = 'e927_alipay_payouts'
down_revision = 'e926_subsidy_campaigns'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('alipay_accounts',
        sa.Column('member_id', sa.Integer(), primary_key=True),
        sa.Column('account', sa.String(128), nullable=False),
        sa.Column('real_name', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('withdrawal_payouts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('withdrawal_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('request_key', sa.String(128), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('coin_cost', sa.Numeric(20, 6), nullable=False),
        sa.Column('account', sa.String(128), nullable=False),
        sa.Column('real_name', sa.String(64), nullable=False),
        sa.Column('out_biz_no', sa.String(64), nullable=False, unique=True),
        sa.Column('provider_scope', sa.String(128), nullable=False),
        sa.Column('provider_order_id', sa.String(128), nullable=False),
        sa.Column('state', sa.String(32), nullable=False),
        sa.Column('error', sa.String(512), nullable=False),
        sa.Column('next_query_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('member_id', 'request_key', name='uq_payout_member_request'))
    op.create_index('ix_withdrawal_payouts_member_id', 'withdrawal_payouts', ['member_id'])
    op.create_index('ix_withdrawal_payouts_state', 'withdrawal_payouts', ['state'])


def downgrade():
    op.drop_table('withdrawal_payouts')
    op.drop_table('alipay_accounts')
