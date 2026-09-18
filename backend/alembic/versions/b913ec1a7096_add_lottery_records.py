"""Independent lottery records for the game user-data dialog."""
from alembic import op
import sqlalchemy as sa

revision = 'b913ec1a7096'
down_revision = 'a913db096f85'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('lottery_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('lottery_price', sa.Float(), nullable=False, server_default='0'),
        sa.Column('ecpm', sa.Float(), nullable=False, server_default='0'),
        sa.Column('adn_name', sa.String(128), nullable=False, server_default=''),
        sa.Column('ip', sa.String(64), nullable=False, server_default=''),
        sa.Column('network_status', sa.Integer(), nullable=True),
        sa.Column('tag', sa.String(255), nullable=False, server_default=''),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('ad_network_rit_id', sa.String(128), nullable=False, server_default=''),
        sa.Column('request_id', sa.String(128), nullable=False, server_default=''),
        sa.Column('trans_id', sa.String(128), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_lottery_records_user_id', 'lottery_records', ['user_id'])
    op.create_index('ix_lottery_records_game_id', 'lottery_records', ['game_id'])


def downgrade():
    op.drop_table('lottery_records')
