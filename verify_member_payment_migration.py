"""Upgrade a temporary old-schema database; preserve unrelated member identity."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'migration.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+path.as_posix()}
    def migrate(target):
        subprocess.run([sys.executable,'-m','alembic','upgrade',target],env=env,check=True,capture_output=True,text=True)
    migrate('d913fe3c92b8')
    with closing(sqlite3.connect(path)) as db:
        # Insert using defaults from the actual pre-change schema.
        columns=db.execute('PRAGMA table_info(members)').fetchall()
        values={name:(0 if 'INT' in kind.upper() or 'FLOAT' in kind.upper() else '') for _,name,kind,required,default,pk in columns if required and default is None and not pk}
        values.update(username='legacy-member',real_name='实名不应冒充收款姓名',created_at='2026-09-16 00:00:00',updated_at='2026-09-16 00:00:00')
        keys=list(values)
        db.execute('INSERT INTO members ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[values[k] for k in keys]);db.commit()
    migrate('head')
    with closing(sqlite3.connect(path)) as db:
        assert db.execute('SELECT username, real_name, receive_name FROM members').fetchone()==('legacy-member','实名不应冒充收款姓名','')
        assert db.execute('SELECT realname_enable FROM members').fetchone()==(None,)
        assert db.execute('SELECT otherlevel FROM members').fetchone()==('',)
        db.execute('UPDATE members SET otherlevel=?',('legacy extra info',));db.commit()
        assert db.execute('SELECT password_hash, password_salt, pay_password_hash, pay_password_salt FROM members').fetchone()==('', '', '', '')
        db.execute('UPDATE members SET receive_name=?',('独立收款人',));db.commit()
        db.execute('UPDATE members SET realname_enable=1');db.commit()
    migrate('head')
    with closing(sqlite3.connect(path)) as db:
        assert db.execute('SELECT receive_name FROM members').fetchone()==('独立收款人',)
        assert db.execute('SELECT realname_enable FROM members').fetchone()==(1,)
        assert db.execute('SELECT otherlevel FROM members').fetchone()==('legacy extra info',)
print('Member migrations: identity preserved, separate payment name, unknown historical real-name state, persisted values survive repeat upgrade')
