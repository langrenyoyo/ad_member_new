"""Member insight and observation records."""
from alembic import op
import sqlalchemy as sa

revision = 'e930_member_insights'
down_revision = 'e929_member_policy'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('device_observations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('member_id', sa.Integer(), nullable=False, index=True),
        sa.Column('game_id', sa.Integer(), nullable=False, index=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=False),
        sa.Column('battery', sa.Integer(), nullable=False),
        sa.Column('charging', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

def downgrade():
    op.drop_table('device_observations')
