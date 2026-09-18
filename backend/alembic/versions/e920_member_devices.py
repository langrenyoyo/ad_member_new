"""Persist member device state and reported application usage."""
from alembic import op
import sqlalchemy as sa

revision = 'e920_member_devices'
down_revision = 'e919_member_otherlevel'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('member_devices',
        sa.Column('user_id', sa.Integer(), primary_key=True),
        *[sa.Column(name, sa.String(length), nullable=False, server_default='') for name, length in [
            ('device_id',128),('imei',128),('android_version',64),('model',128),('app_version',64),('ip_address',255),('sim_info',255)]],
        *[sa.Column(name,sa.Integer(),nullable=True) for name in ['risk_flag','usb_debugging','rooted','total_clicks','today_clicks','today_failed']],
        sa.Column('device_id_ban',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('imei_id_ban',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('counter_date',sa.Date(),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('member_app_usage',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),nullable=False),sa.Column('game_id',sa.Integer(),nullable=False),
        sa.Column('app_name',sa.String(255),nullable=False,server_default=''),sa.Column('package_name',sa.String(255),nullable=False,server_default=''),
        sa.Column('count',sa.Integer(),nullable=False,server_default='0'),sa.Column('duration_seconds',sa.Float(),nullable=False,server_default='0'),
        sa.Column('first_used_at',sa.DateTime(timezone=True),nullable=True),sa.Column('last_used_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_member_app_usage_user_id','member_app_usage',['user_id'])
    op.create_index('ix_member_app_usage_game_id','member_app_usage',['game_id'])


def downgrade():
    op.drop_table('member_app_usage')
    op.drop_table('member_devices')
