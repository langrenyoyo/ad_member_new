"""Migrate wallet accounting to six-decimal coins, retaining original values."""
from decimal import Decimal, ROUND_DOWN
from alembic import op
import sqlalchemy as sa

revision = 'e932_wallet_decimal'
down_revision = 'e931b_app_foundation'
branch_labels = None
depends_on = None

TABLES = {
    'members': ['coin', 'freeze_coin', 'coin_user', 'coin_user_month', 'coin_user_day'],
    'coin_logs': ['coin_before', 'coin', 'coin_after'],
    'app_ad_sessions': ['reward_coin'],
}


def upgrade():
    bind = op.get_bind()
    # Values are retained independently of the new schema for migration reconciliation.
    archive = op.create_table('wallet_decimal_migration_values',
        sa.Column('table_name', sa.String(64), primary_key=True),
        sa.Column('row_id', sa.String(80), primary_key=True),
        sa.Column('column_name', sa.String(64), primary_key=True),
        sa.Column('original_value', sa.String(128), nullable=False),
        sa.Column('decimal_value', sa.String(128), nullable=False))
    for table, columns in TABLES.items():
        records = bind.execute(sa.text(f'SELECT id, {", ".join(columns)} FROM {table}')).mappings()
        batch = []
        for row in records:
            for column in columns:
                value = Decimal(str(row[column]))
                if not value.is_finite() or abs(value) >= Decimal('1000000000000000000'):
                    raise RuntimeError(f'Invalid wallet value: {table}/{row["id"]}/{column}')
                converted = value.quantize(Decimal('.000001'), rounding=ROUND_DOWN)
                batch.append(dict(table_name=table, row_id=str(row['id']), column_name=column,
                    original_value=str(value), decimal_value=str(converted)))
            if len(batch) >= 1000:
                bind.execute(archive.insert(), batch); batch = []
        if batch: bind.execute(archive.insert(), batch)
        with op.batch_alter_table(table) as alter:
            for column in columns:
                alter.alter_column(column, existing_type=sa.Float(), type_=sa.Numeric(24, 6),
                    existing_nullable=False,
                    postgresql_using=f'trunc({column}::text::numeric, 6)')
        # SQLite has no decimal-native storage; use the same truncation semantics locally.
        if bind.dialect.name == 'sqlite':
            for column in columns:
                bind.execute(sa.text(f'''UPDATE {table} SET {column} = (
                    SELECT decimal_value FROM wallet_decimal_migration_values
                    WHERE table_name=:table AND column_name=:column AND row_id=CAST({table}.id AS TEXT))'''),
                    {'table': table, 'column': column})


def downgrade():
    raise RuntimeError('Wallet precision downgrade is lossy; restore an audited backup instead.')
