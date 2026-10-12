"""Member onboarding, SMS, usage and settlement ledgers."""
from alembic import op
import sqlalchemy as sa
revision = 'e929_member_policy'
down_revision = 'e928_device_risk'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('member_enrollments',
        sa.Column('member_id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('invite_code', sa.String(length=32), primary_key=False, nullable=False),
        sa.Column('parent_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('level', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('usage_granted', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('usage_seen_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint('invite_code', name=None),
    )
    op.create_table('member_usage_reports',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('report_date', sa.String(length=10), primary_key=False, nullable=False),
        sa.Column('package_name', sa.String(length=255), primary_key=False, nullable=False),
        sa.Column('duration_ms', sa.BigInteger(), primary_key=False, nullable=False),
        sa.Column('opens', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint('member_id', 'report_date', 'package_name', name='uq_member_usage_day_package'),
    )
    op.create_index('ix_member_usage_reports_member_id', 'member_usage_reports', ['member_id'], unique=False)
    op.create_table('member_reward_ledgers',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ad_session_id', sa.String(length=80), primary_key=False, nullable=False),
        sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('beneficiary_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('kind', sa.String(length=32), primary_key=False, nullable=False),
        sa.Column('amount', sa.Numeric(precision=24, scale=6), primary_key=False, nullable=False),
        sa.Column('rule_json', sa.Text(), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint('ad_session_id', 'beneficiary_id', 'kind', name='uq_ad_beneficiary_kind'),
    )
    op.create_index('ix_member_reward_ledgers_ad_session_id', 'member_reward_ledgers', ['ad_session_id'], unique=False)
    op.create_index('ix_member_reward_ledgers_beneficiary_id', 'member_reward_ledgers', ['beneficiary_id'], unique=False)
    op.create_index('ix_member_reward_ledgers_member_id', 'member_reward_ledgers', ['member_id'], unique=False)
    op.create_index('ix_member_reward_ledgers_game_id', 'member_reward_ledgers', ['game_id'], unique=False)
    op.create_table('device_login_cooldowns',
        sa.Column('device_id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('blocked_until', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_table('app_sms_codes',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('phone_hash', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('ip_hash', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('code_hash', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('attempts', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('state', sa.String(length=16), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_index('ix_app_sms_codes_game_id', 'app_sms_codes', ['game_id'], unique=False)
    op.create_index('ix_app_sms_codes_phone_hash', 'app_sms_codes', ['phone_hash'], unique=False)
    op.create_index('ix_app_sms_codes_ip_hash', 'app_sms_codes', ['ip_hash'], unique=False)

def downgrade():
    op.drop_table('app_sms_codes')
    op.drop_table('device_login_cooldowns')
    op.drop_table('member_reward_ledgers')
    op.drop_table('member_usage_reports')
    op.drop_table('member_enrollments')
