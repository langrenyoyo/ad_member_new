"""Persist the administrator's uploaded profile avatar."""
from alembic import op
import sqlalchemy as sa

revision = 'e922_admin_avatar'
down_revision = 'e921_withdrawal_blacklist'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('admin_users', sa.Column('avatar', sa.String(1024), nullable=False, server_default='/assets/img/avatar.png'))


def downgrade():
    op.drop_column('admin_users', 'avatar')
