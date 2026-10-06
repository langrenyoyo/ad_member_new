"""Verified device risk rules and atomic ad admissions."""
from alembic import op
import sqlalchemy as sa
revision = 'e928_device_risk'
down_revision = 'e927_alipay_payouts'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('device_risk_rules',
        sa.Column('game_id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('enabled', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('limit_enabled', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('daily_limit', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('risk_days', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('reset_tags', sa.Text(), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_table('risk_devices',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('device_key', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('tags', sa.Text(), primary_key=False, nullable=False),
        sa.Column('reason', sa.String(length=255), primary_key=False, nullable=False),
        sa.Column('risk_until', sa.DateTime(timezone=True), primary_key=False, nullable=True),
        sa.Column('override', sa.String(length=16), primary_key=False, nullable=False),
        sa.Column('last_member_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint('game_id', 'device_key', name='uq_risk_game_device'),
    )
    op.create_index('ix_risk_devices_game_id', 'risk_devices', ['game_id'], unique=False)
    op.create_table('risk_device_installs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('device_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('install_hash', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint('device_id', 'install_hash', name='uq_risk_device_install'),
    )
    op.create_index('ix_risk_device_installs_device_id', 'risk_device_installs', ['device_id'], unique=False)
    op.create_table('device_risk_checks',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('install_hash', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
        sa.Column('device_id', sa.Integer(), primary_key=False, nullable=True),
        sa.Column('token_hash', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('provider_request_id', sa.String(length=128), primary_key=False, nullable=False),
        sa.Column('status', sa.String(length=32), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
    )
    op.create_index('ix_device_risk_checks_device_id', 'device_risk_checks', ['device_id'], unique=False)
    op.create_index('ix_device_risk_checks_game_id', 'device_risk_checks', ['game_id'], unique=False)
    op.create_index('ix_device_risk_checks_member_id', 'device_risk_checks', ['member_id'], unique=False)
    op.create_table('device_ad_admissions',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('device_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
        sa.Column('ad_session_id', sa.String(length=80), primary_key=False, nullable=False),
        sa.Column('check_id', sa.String(length=64), primary_key=False, nullable=False),
        sa.Column('quota_date', sa.Date(), primary_key=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        sa.UniqueConstraint('ad_session_id', name=None),
        sa.UniqueConstraint('check_id', name=None),
    )
    op.create_index('ix_device_ad_admissions_device_id', 'device_ad_admissions', ['device_id'], unique=False)
    op.create_index('ix_device_ad_admissions_game_id', 'device_ad_admissions', ['game_id'], unique=False)
    op.create_index('ix_device_ad_admissions_member_id', 'device_ad_admissions', ['member_id'], unique=False)
    op.create_index('ix_device_ad_admissions_quota_date', 'device_ad_admissions', ['quota_date'], unique=False)

def downgrade():
    op.drop_table('device_ad_admissions')
    op.drop_table('device_risk_checks')
    op.drop_table('risk_device_installs')
    op.drop_table('risk_devices')
    op.drop_table('device_risk_rules')
