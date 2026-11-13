"""Daily consented application inventory snapshots, compatible with old usage reports."""
from alembic import op
import sqlalchemy as sa

revision = 'e940_usage_inventory'
down_revision = 'e939_six_char_invite_codes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('member_usage_snapshots',
        sa.Column('member_id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('report_date', sa.String(10), primary_key=True, nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('inventory_json', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False))


def downgrade():
    op.drop_table('member_usage_snapshots')
