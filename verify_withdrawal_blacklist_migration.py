"""Round-trip the recipient blacklist schema in disposable SQLite."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    database=Path(directory)/'blacklist.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+database.as_posix(),'APP_ENV':'development'}
    def migrate(action,target):
        result=subprocess.run([sys.executable,'-m','alembic',action,target],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    migrate('upgrade','e920_member_devices')
    with closing(sqlite3.connect(database)) as db:
        db.execute("INSERT INTO member_devices (user_id,created_at,updated_at) VALUES (42,'2026-09-18','2026-09-18')");db.commit()
    migrate('upgrade','e921_withdrawal_blacklist')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('e921_withdrawal_blacklist',)
        db.execute("INSERT INTO withdrawal_blacklist (receive_name,receive_tel,created_at,updated_at) VALUES ('fixture','00123','2026-09-18','2026-09-18')")
        assert db.execute('SELECT status,source_withdrawal_id FROM withdrawal_blacklist').fetchone()==(1,0)
        try:db.execute("INSERT INTO withdrawal_blacklist (receive_name,receive_tel,created_at,updated_at) VALUES ('fixture','00123','2026-09-18','2026-09-18')")
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('Duplicate recipient accepted')
        db.commit()
    migrate('upgrade','e921_withdrawal_blacklist')
    with closing(sqlite3.connect(database)) as db:assert db.execute('SELECT COUNT(*) FROM withdrawal_blacklist').fetchone()==(1,)
    migrate('downgrade','e920_member_devices')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT user_id FROM member_devices').fetchone()==(42,)
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='withdrawal_blacklist'").fetchall()
    migrate('upgrade','e921_withdrawal_blacklist')
    with closing(sqlite3.connect(database)) as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
print('Blacklist migration: defaults, unique recipients, repeat upgrade, scoped downgrade and re-upgrade passed')
