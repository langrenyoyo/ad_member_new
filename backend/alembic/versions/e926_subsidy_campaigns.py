"""Subsidy campaign configuration and durable quota reservations."""
from alembic import op
import sqlalchemy as sa

revision = 'e926_subsidy_campaigns'
down_revision = 'e925_game_taku_configs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('subsidy_campaigns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(128), nullable=False),
        sa.Column('enabled', sa.Integer(), nullable=False),
        sa.Column('daily_quota', sa.Integer(), nullable=False),
        sa.Column('withdrawal_cents', sa.Integer(), nullable=False),
        sa.Column('recharge_cents', sa.Integer(), nullable=False),
        sa.Column('reward_cents', sa.Integer(), nullable=False),
        sa.Column('review_hours', sa.Integer(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_subsidy_campaigns_game_id', 'subsidy_campaigns', ['game_id'])
    op.create_table('subsidy_reservations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('subsidy_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('quota_date', sa.Date(), nullable=False),
        sa.Column('request_key', sa.String(128), nullable=False),
        sa.Column('request_json', sa.Text(), nullable=False),
        sa.Column('snapshot_json', sa.Text(), nullable=False),
        sa.Column('review_due_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('campaign_id', 'member_id', 'quota_date', name='uq_subsidy_daily_member'),
        sa.UniqueConstraint('member_id', 'request_key', name='uq_subsidy_request_key'))
    for field in ['campaign_id', 'member_id', 'quota_date']:
        op.create_index('ix_subsidy_reservations_' + field, 'subsidy_reservations', [field])


def downgrade():
    op.drop_table('subsidy_reservations')
    op.drop_table('subsidy_campaigns')
