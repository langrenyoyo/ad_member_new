import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest


def test_migration_preserves_history_and_only_releases_rejected_slots():
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/e942_subsidy_retry.py'
    spec = importlib.util.spec_from_file_location('retry_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE subsidies (id INTEGER PRIMARY KEY, status INTEGER)')
        conn.exec_driver_sql('INSERT INTO subsidies VALUES (1,2),(2,0)')
        conn.exec_driver_sql('''CREATE TABLE subsidy_reservations (
            id INTEGER PRIMARY KEY, campaign_id INTEGER, member_id INTEGER,
            quota_date TEXT, subsidy_id INTEGER UNIQUE, request_key TEXT,
            CONSTRAINT uq_subsidy_daily_member UNIQUE (campaign_id,member_id,quota_date),
            CONSTRAINT uq_subsidy_request_key UNIQUE (member_id,request_key))''')
        conn.exec_driver_sql("INSERT INTO subsidy_reservations VALUES (1,1,1,'2026-11-17',1,'a'),(2,1,2,'2026-11-17',2,'b')")
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert conn.exec_driver_sql('SELECT active FROM subsidy_reservations ORDER BY id').fetchall() == [(0,), (1,)]
        conn.exec_driver_sql("INSERT INTO subsidy_reservations VALUES (3,1,1,'2026-11-17',3,'c',1)")
        with pytest.raises(sa.exc.IntegrityError):
            conn.exec_driver_sql("INSERT INTO subsidy_reservations VALUES (4,1,1,'2026-11-17',4,'d',1)")
