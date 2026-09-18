"""Persist the reference member editor's other information field."""
from alembic import op
import sqlalchemy as sa

revision = 'e919_member_otherlevel'
down_revision = 'e918_member_lottery_repair'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('members', sa.Column('otherlevel', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('members', 'otherlevel')
