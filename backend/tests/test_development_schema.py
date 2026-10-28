import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import main_from_txt as m


class DevelopmentSchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as conn:
            conn.execute(text('CREATE TABLE members (id INTEGER PRIMARY KEY, coin NUMERIC(24,6))'))
            conn.execute(text('INSERT INTO members VALUES (7, 12.345678)'))
            conn.execute(text('CREATE TABLE ad_records (id INTEGER PRIMARY KEY, ad_group VARCHAR(32), ecpm FLOAT)'))
            conn.execute(text("INSERT INTO ad_records VALUES (9, 'main', 123.45)"))

    def test_legacy_development_database_is_repaired_without_losing_values(self):
        with patch.object(m, 'engine', self.engine), patch.object(m, 'APP_ENV', 'development'):
            m.ensure_development_schema()
            with self.engine.begin() as conn:
                row = conn.execute(text('SELECT callback_ecpm, callback_price_currency, gps_ip_cross_region, risk_tags_json FROM ad_records')).one()
                self.assertEqual(tuple(row), (None, '', 0, '[]'))
                conn.execute(text("UPDATE ad_records SET callback_ecpm=120, callback_price_currency='CNY', gps_ip_cross_region=1, risk_tags_json='[1]'"))
                conn.execute(text('UPDATE members SET whitelist_min_coin=0.01, whitelist_max_coin=0.02'))
            m.ensure_development_schema()
        with self.engine.connect() as conn:
            self.assertEqual(tuple(conn.execute(text('SELECT id, coin, whitelist_min_coin, whitelist_max_coin FROM members')).one()), (7, 12.345678, 0.01, 0.02))
            self.assertEqual(tuple(conn.execute(text('SELECT id, ecpm, callback_ecpm, callback_price_currency, gps_ip_cross_region, risk_tags_json FROM ad_records')).one()), (9, 123.45, 120, 'CNY', 1, '[1]'))
        self.assertTrue({'client_ecpm', 'settlement_ecpm', 'attention_count'} <= {c['name'] for c in inspect(self.engine).get_columns('ad_records')})

    def test_production_still_requires_explicit_migrations(self):
        with patch.object(m, 'engine', self.engine), patch.object(m, 'APP_ENV', 'production'):
            m.ensure_development_schema()
        self.assertNotIn('callback_ecpm', {c['name'] for c in inspect(self.engine).get_columns('ad_records')})
        self.assertNotIn('whitelist_min_coin', {c['name'] for c in inspect(self.engine).get_columns('members')})
