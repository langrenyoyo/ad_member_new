"""Independent daily active records for game user-data."""
from alembic import op
import sqlalchemy as sa
revision='d913fe3c92b8'; down_revision='c913fd2b81a7'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('daily_activity', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('game_id',sa.Integer(),nullable=False), sa.Column('date',sa.Date(),nullable=False), sa.Column('num',sa.Integer(),nullable=False,server_default='0'))
    op.create_index('ix_daily_activity_game_id','daily_activity',['game_id']); op.create_index('ix_daily_activity_date','daily_activity',['date'])
def downgrade(): op.drop_table('daily_activity')
