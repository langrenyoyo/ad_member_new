"""Versioned TAKU device report reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = 'e935_taku_reports'
down_revision = 'e934_taku_global_keys'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('taku_report_rules', sa.Column('game_id', sa.Integer(), primary_key=True),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('taku_report_batches', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('game_id', sa.Integer(), nullable=False, index=True),
        sa.Column('day', sa.String(10), nullable=False, index=True),
        sa.Column('digest', sa.String(64), nullable=False), sa.Column('stage', sa.String(20), nullable=False),
        sa.Column('rows_json', sa.Text(), nullable=False), sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('taku_report_batches')
    op.drop_table('taku_report_rules')
