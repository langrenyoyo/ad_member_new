"""Independent reference game moderation status and lottery anomaly percentage."""
from alembic import op
import sqlalchemy as sa
revision='f912caf85e74'
down_revision='e912b9f74d63'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('games',sa.Column('game_ad_status',sa.Integer(),nullable=True))
    op.add_column('games',sa.Column('game_lottery_num',sa.Float(),nullable=True))
def downgrade():
    op.drop_column('games','game_lottery_num')
    op.drop_column('games','game_ad_status')
