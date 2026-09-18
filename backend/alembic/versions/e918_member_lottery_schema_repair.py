"""Repair databases stamped before e916 gained the second lottery fields.

Keep e916 unchanged: deployed variants exist with and without those columns.
"""
from alembic import op
import sqlalchemy as sa

revision = 'e918_member_lottery_repair'
down_revision = 'e917_member_password_hashes'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    columns = {column['name']: column for column in sa.inspect(connection).get_columns('members')}
    for name, typ in [('raffle_num2', sa.Integer()), ('star_countdown2', sa.Float()), ('over_countdown2', sa.Float())]:
        if name not in columns:
            op.add_column('members', sa.Column(name, typ, nullable=True))
    members = sa.table('members', sa.column('down_load', sa.String(255)))
    connection.execute(members.update().where(members.c.down_load.is_(None)).values(down_load=''))
    if columns['down_load']['nullable']:
        with op.batch_alter_table('members') as batch:
            batch.alter_column('down_load', existing_type=sa.String(255), nullable=False)


def downgrade():
    # Both e916 variants own the lottery columns; retaining them preserves data
    # and avoids deleting columns that existed before this repair was applied.
    with op.batch_alter_table('members') as batch:
        batch.alter_column('down_load', existing_type=sa.String(255), nullable=True)
