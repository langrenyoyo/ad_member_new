"""Retain rejected applications while restoring their daily campaign slot."""
from alembic import op
import sqlalchemy as sa

revision = 'e942_subsidy_retry'
down_revision = 'e941_system_password'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('subsidy_reservations') as batch:
        batch.add_column(sa.Column('active', sa.Integer(), nullable=False, server_default='1'))
        batch.drop_constraint('uq_subsidy_daily_member', type_='unique')
    op.execute('UPDATE subsidy_reservations SET active=0 WHERE subsidy_id IN (SELECT id FROM subsidies WHERE status=2)')
    op.create_index('uq_subsidy_active_daily', 'subsidy_reservations',
                    ['campaign_id', 'member_id', 'quota_date'], unique=True,
                    sqlite_where=sa.text('active=1'), postgresql_where=sa.text('active=1'))


def downgrade():
    raise RuntimeError('Restored slots may have been reused; retain application history and migrate forward.')
