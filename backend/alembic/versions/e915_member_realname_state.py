"""Store explicit member real-name state without inferring historical verification."""
from alembic import op
import sqlalchemy as sa

revision = 'e915_member_realname_state'
down_revision = 'e914_member_receive_name'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('members', sa.Column('realname_enable', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('members', 'realname_enable')
