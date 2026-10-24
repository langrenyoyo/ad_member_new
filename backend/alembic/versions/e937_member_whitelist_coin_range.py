"""Add per-member whitelist reward ranges."""
from alembic import op
import sqlalchemy as sa

revision = 'e937_member_whitelist_coin_range'
down_revision = 'e936_ad_diagnostics'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('members', sa.Column('whitelist_min_coin', sa.Numeric(24, 6), nullable=True))
    op.add_column('members', sa.Column('whitelist_max_coin', sa.Numeric(24, 6), nullable=True))


def downgrade():
    op.drop_column('members', 'whitelist_max_coin')
    op.drop_column('members', 'whitelist_min_coin')
