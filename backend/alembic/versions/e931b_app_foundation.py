"""Repair missing APP foundation tables on migration-only installations."""
from alembic import op
import sqlalchemy as sa
revision = 'e931b_app_foundation'
down_revision = 'e931_ad_category_reviews'
branch_labels = None
depends_on = None

def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table, column, length in [('admin_users', 'mobile', 32), ('members', 'ip', 64)]:
        if column not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column(column, sa.String(length), nullable=False, server_default=''))
    if 'ad_flow_logs' not in existing:
        op.create_table('ad_flow_logs',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('ad_session_id', sa.String(length=80), primary_key=False, nullable=False),
            sa.Column('request_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('event_type', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('status', sa.String(length=32), primary_key=False, nullable=False),
            sa.Column('provider', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('trans_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('error_code', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('detail_json', sa.Text(), primary_key=False, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        )
        op.create_index('ix_ad_flow_logs_ad_session_id', 'ad_flow_logs', ['ad_session_id'], unique=False)
        op.create_index('ix_ad_flow_logs_event_type', 'ad_flow_logs', ['event_type'], unique=False)
        op.create_index('ix_ad_flow_logs_game_id', 'ad_flow_logs', ['game_id'], unique=False)
        op.create_index('ix_ad_flow_logs_member_id', 'ad_flow_logs', ['member_id'], unique=False)
        op.create_index('ix_ad_flow_logs_request_id', 'ad_flow_logs', ['request_id'], unique=False)
        op.create_index('ix_ad_flow_logs_status', 'ad_flow_logs', ['status'], unique=False)
        op.create_index('ix_ad_flow_logs_trans_id', 'ad_flow_logs', ['trans_id'], unique=False)
    if 'admin_operations' not in existing:
        op.create_table('admin_operations',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('admin_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('title', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('path', sa.String(length=255), primary_key=False, nullable=False),
            sa.Column('ip', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        )
        op.create_index('ix_admin_operations_admin_id', 'admin_operations', ['admin_id'], unique=False)
    if 'app_ad_events' not in existing:
        op.create_table('app_ad_events',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('event_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('ad_session_id', sa.String(length=80), primary_key=False, nullable=False),
            sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('event_type', sa.String(length=32), primary_key=False, nullable=False),
            sa.Column('result_json', sa.Text(), primary_key=False, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.UniqueConstraint('event_id', name='uq_app_ad_event_id'),
        )
        op.create_index('ix_app_ad_events_ad_session_id', 'app_ad_events', ['ad_session_id'], unique=False)
        op.create_index('ix_app_ad_events_event_id', 'app_ad_events', ['event_id'], unique=False)
        op.create_index('ix_app_ad_events_member_id', 'app_ad_events', ['member_id'], unique=False)
    if 'app_ad_sessions' not in existing:
        op.create_table('app_ad_sessions',
            sa.Column('id', sa.String(length=80), primary_key=True, nullable=False),
            sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('agent_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('game_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('device_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('client_request_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('request_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('placement', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('ad_type', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('provider', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('ad_unit_id', sa.String(length=255), primary_key=False, nullable=False),
            sa.Column('reward_coin', sa.Float(), primary_key=False, nullable=False),
            sa.Column('status', sa.String(length=32), primary_key=False, nullable=False),
            sa.Column('session_token_hash', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('impressed_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
            sa.Column('failed_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
            sa.Column('coin_log_id', sa.Integer(), primary_key=False, nullable=True),
            sa.Column('result_json', sa.Text(), primary_key=False, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        )
        op.create_index('ix_app_ad_sessions_agent_id', 'app_ad_sessions', ['agent_id'], unique=False)
        op.create_index('ix_app_ad_sessions_game_id', 'app_ad_sessions', ['game_id'], unique=False)
        op.create_index('ix_app_ad_sessions_member_id', 'app_ad_sessions', ['member_id'], unique=False)
        op.create_index('ix_app_ad_sessions_request_id', 'app_ad_sessions', ['request_id'], unique=True)
    if 'app_refresh_sessions' not in existing:
        op.create_table('app_refresh_sessions',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('token_hash', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('device_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
            sa.Column('last_used_at', sa.DateTime(timezone=True), primary_key=False, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
        )
        op.create_index('ix_app_refresh_sessions_member_id', 'app_refresh_sessions', ['member_id'], unique=False)
        op.create_index('ix_app_refresh_sessions_token_hash', 'app_refresh_sessions', ['token_hash'], unique=True)
    if 'wechat_identities' not in existing:
        op.create_table('wechat_identities',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('member_id', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('provider', sa.String(length=32), primary_key=False, nullable=False),
            sa.Column('app_id', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('openid', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('unionid', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('nickname', sa.String(length=128), primary_key=False, nullable=False),
            sa.Column('avatar_url', sa.String(length=512), primary_key=False, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), primary_key=False, nullable=False),
            sa.UniqueConstraint('provider', 'app_id', 'openid', name='uq_wechat_identity_provider_app_openid'),
        )
        op.create_index('ix_wechat_identities_member_id', 'wechat_identities', ['member_id'], unique=False)


def downgrade():
    raise RuntimeError('Foundation tables may predate this migration; restore a backup to downgrade.')
