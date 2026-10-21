"""Ad diagnostics for callback/client price comparison and risk labels."""
from alembic import op
import sqlalchemy as sa

revision = 'e936_ad_diagnostics'
down_revision = 'e935_taku_reports'
branch_labels = None
depends_on = None


def upgrade():
    for name, column in [
        ('callback_ecpm', sa.Float()), ('client_ecpm', sa.Float()), ('settlement_ecpm', sa.Float()),
        ('callback_price_currency', sa.String(8)), ('attention_count', sa.Integer()),
        ('gps_ip_cross_region', sa.Integer()), ('risk_tags_json', sa.Text()),
    ]:
        op.add_column('ad_records', sa.Column(name, column, nullable=True))
    op.execute("UPDATE ad_records SET callback_price_currency='', gps_ip_cross_region=0, risk_tags_json='[]' WHERE callback_price_currency IS NULL")


def downgrade():
    for name in ('risk_tags_json','gps_ip_cross_region','attention_count','callback_price_currency','settlement_ecpm','client_ecpm','callback_ecpm'):
        op.drop_column('ad_records', name)
