"""Upgrade/downgrade device tables in a disposable SQLite database."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path


root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as directory:
    database = Path(directory) / 'devices.db'
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + database.as_posix(), 'APP_ENV': 'development'}

    def migrate(action, target):
        result = subprocess.run([sys.executable, '-m', 'alembic', action, target], cwd=root,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    migrate('upgrade', 'e919_member_otherlevel')
    with closing(sqlite3.connect(database)) as db:
        db.execute('CREATE TABLE preserved_fixture (value TEXT)')
        db.execute('INSERT INTO preserved_fixture VALUES (?)', ('preserved',))
        db.commit()
    migrate('upgrade', 'e920_member_devices')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('e920_member_devices',)
        db.execute("INSERT INTO member_devices (user_id,created_at,updated_at) VALUES (42,'2026-09-18','2026-09-18')")
        assert db.execute('SELECT device_id,imei,device_id_ban,imei_id_ban,total_clicks,today_clicks,counter_date FROM member_devices').fetchone() == ('', '', 0, 0, None, None, None)
        db.execute("INSERT INTO member_app_usage (user_id,game_id,created_at,updated_at) VALUES (42,237,'2026-09-18','2026-09-18')")
        assert db.execute('SELECT app_name,package_name,count,duration_seconds,first_used_at,last_used_at FROM member_app_usage').fetchone() == ('', '', 0, 0, None, None)
        indexes = {row[1] for row in db.execute('PRAGMA index_list(member_app_usage)')}
        assert {'ix_member_app_usage_user_id', 'ix_member_app_usage_game_id'} <= indexes
        db.commit()
    migrate('upgrade', 'head')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT COUNT(*) FROM member_devices').fetchone() == (1,)
    migrate('downgrade', 'e919_member_otherlevel')
    with closing(sqlite3.connect(database)) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not {'member_devices', 'member_app_usage'} & tables
        assert db.execute('SELECT value FROM preserved_fixture').fetchone() == ('preserved',)
        assert 'members' in tables
    migrate('upgrade', 'head')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)

print('Device migration: upgrade, defaults/indexes, repeat upgrade, scoped downgrade and re-upgrade passed')
