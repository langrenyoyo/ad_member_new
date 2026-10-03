"""Private per-game TAKU callback configuration."""
from alembic import op
import sqlalchemy as sa

revision = 'e925_game_taku_configs'
down_revision = 'e924_kuaishou_risk_assessments'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('game_taku_configs',
        sa.Column('game_id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Integer(), nullable=False),
        sa.Column('sec_key', sa.String(512), nullable=False))

def downgrade():
    op.drop_table('game_taku_configs')
