"""Independent historical member login records, never inferred from last login."""
from alembic import op
import sqlalchemy as sa
revision='a913db096f85'
down_revision='f912caf85e74'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('member_login_logs',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),nullable=False),
        sa.Column('game_id',sa.Integer(),nullable=False),
        sa.Column('device_id',sa.String(128),nullable=False,server_default=''),
        sa.Column('ip',sa.String(64),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_member_login_logs_user_id','member_login_logs',['user_id'])
    op.create_index('ix_member_login_logs_game_id','member_login_logs',['game_id'])
def downgrade():
    op.drop_table('member_login_logs')
