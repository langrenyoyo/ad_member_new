"""Persist recipient blacklist independently of member account state."""
from alembic import op
import sqlalchemy as sa

revision = 'e921_withdrawal_blacklist'
down_revision = 'e920_member_devices'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('withdrawal_blacklist',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('receive_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('receive_tel', sa.String(64), nullable=False, server_default=''),
        sa.Column('status', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_withdrawal_id', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('receive_name', 'receive_tel', name='uq_withdrawal_blacklist_recipient'))


def downgrade():
    op.drop_table('withdrawal_blacklist')
