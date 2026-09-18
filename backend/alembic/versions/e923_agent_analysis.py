"""Persist per-agent analysis chart ranges."""
from alembic import op
import sqlalchemy as sa

revision = 'e923_agent_analysis'
down_revision = 'e922_admin_avatar'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('agent_analysis_config',
        sa.Column('agent_id', sa.Integer(), primary_key=True),
        sa.Column('buckets', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('agent_analysis_config')
