"""Auditable, manually reviewed ad classifications."""
from alembic import op
import sqlalchemy as sa

revision = 'e931_ad_category_reviews'
down_revision = 'e930_member_insights'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ad_category_reviews',
        sa.Column('ad_session_id', sa.String(80), primary_key=True),
        sa.Column('member_id', sa.Integer(), nullable=False, index=True),
        sa.Column('category', sa.String(32), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('reason', sa.String(1000), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('ad_category_reviews')
