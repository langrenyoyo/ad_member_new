"""Consolidate legacy V2 members into captains; historical snapshots stay intact."""
from alembic import op
import sqlalchemy as sa

revision = 'e938_three_member_roles'
down_revision = 'e937_member_whitelist_coin_range'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text('UPDATE member_enrollments SET level = 1 WHERE level = 2'))


def downgrade():
    # The old role cannot be inferred after members have changed levels.
    pass
