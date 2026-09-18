"""Store withdrawal product, device and review text from source records."""
from alembic import op
import sqlalchemy as sa

revision = "b912e6d41a30"
down_revision = "a4d9f2c8e7b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, size in [('good_name', 255), ('device_manufacturer', 128), ('check_status_txt', 255)]:
        op.add_column('withdrawals', sa.Column(name, sa.String(size), nullable=False, server_default=''))


def downgrade() -> None:
    for name in ['check_status_txt', 'device_manufacturer', 'good_name']:
        op.drop_column('withdrawals', name)
