"""Track explicit system password setup separately from generated OAuth passwords."""
from alembic import op
import sqlalchemy as sa

revision = 'e941_system_password'
down_revision = 'e940_usage_inventory'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('members', sa.Column('system_password_set', sa.Boolean(), nullable=False, server_default='1'))
    # Historical OAuth accounts have no reliable explicit-password marker. Ask them
    # to confirm a password once, without changing any existing password hashes.
    op.execute("UPDATE members SET system_password_set=0 WHERE id IN (SELECT member_id FROM wechat_identities) AND username LIKE 'wx_%'")


def downgrade():
    op.drop_column('members', 'system_password_set')
