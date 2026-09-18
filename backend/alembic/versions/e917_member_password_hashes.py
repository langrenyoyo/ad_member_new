"""Store member and payment passwords as salted hashes."""
from alembic import op
import sqlalchemy as sa
revision='e917_member_password_hashes'
down_revision='e916_member_lottery_download'
branch_labels=None
depends_on=None
def upgrade():
    for name in ('password_hash','password_salt','pay_password_hash','pay_password_salt'):
        op.add_column('members',sa.Column(name,sa.String(255 if 'hash' in name else 64),nullable=False,server_default=''))
def downgrade():
    for name in ('pay_password_salt','pay_password_hash','password_salt','password_hash'):op.drop_column('members',name)
