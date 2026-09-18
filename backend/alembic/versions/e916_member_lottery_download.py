"""Persist member lottery and download settings exposed by reference editor."""
from alembic import op
import sqlalchemy as sa

revision = 'e916_member_lottery_download'
down_revision = 'e915_member_realname_state'
branch_labels = None
depends_on = None

def upgrade():
    for name, typ in [('raffle_open', sa.Integer()), ('raffle_num', sa.Integer()), ('star_countdown', sa.Float()), ('over_countdown', sa.Float()), ('down_load', sa.String(255)), ('raffle_num2', sa.Integer()), ('star_countdown2', sa.Float()), ('over_countdown2', sa.Float())]:
        op.add_column('members', sa.Column(name, typ, nullable=True))

def downgrade():
    for name in ('over_countdown2', 'star_countdown2', 'raffle_num2', 'down_load', 'over_countdown', 'star_countdown', 'raffle_num', 'raffle_open'):
        op.drop_column('members', name)
