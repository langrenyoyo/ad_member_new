"""Upgrade and round-trip profile avatars in disposable SQLite, preserving identities."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    database = Path(directory)/'profile.db'
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///'+database.as_posix(), 'APP_ENV': 'development'}
    def migrate(action, target):
        result = subprocess.run([sys.executable, '-m', 'alembic', action, target], cwd=Path(__file__).resolve().parent, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout+result.stderr
    migrate('upgrade', 'e921_withdrawal_blacklist')
    with closing(sqlite3.connect(database)) as db:
        db.execute("INSERT INTO admin_users (username,password_hash,password_salt,display_name,role,status,created_at,updated_at) VALUES ('fixture','preserved-hash','preserved-salt','Fixture','risk',1,'2026-09-18','2026-09-18')")
        db.commit()
    migrate('upgrade', 'e922_admin_avatar')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('e922_admin_avatar',)
        assert db.execute('SELECT avatar FROM admin_users').fetchone() == ('/assets/img/avatar.png',)
        avatar = '/api/member-images/'+'a'*48+'.png'
        db.execute('UPDATE admin_users SET avatar=?', (avatar,)); db.commit()
    migrate('upgrade', 'e922_admin_avatar')
    with closing(sqlite3.connect(database)) as db: assert db.execute('SELECT avatar FROM admin_users').fetchone() == (avatar,)
    migrate('downgrade', 'e921_withdrawal_blacklist')
    with closing(sqlite3.connect(database)) as db:
        assert 'avatar' not in [row[1] for row in db.execute('PRAGMA table_info(admin_users)')]
        assert db.execute('SELECT username,password_hash,password_salt FROM admin_users').fetchone() == ('fixture','preserved-hash','preserved-salt')
        assert db.execute("SELECT name FROM sqlite_master WHERE name='withdrawal_blacklist'").fetchone()
    migrate('upgrade', 'e922_admin_avatar')
    with closing(sqlite3.connect(database)) as db: assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
print('Profile avatar migration: full chain, defaults, saved path, identity preservation, downgrade and re-upgrade passed')
