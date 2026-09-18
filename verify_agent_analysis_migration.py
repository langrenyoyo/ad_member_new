"""Exercise the analysis settings migration in an isolated SQLite database."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    database=Path(directory)/'analysis.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+database.as_posix(),'APP_ENV':'development'}
    def migrate(action,target):
        result=subprocess.run([sys.executable,'-m','alembic',action,target],cwd=Path(__file__).resolve().parent,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stdout+result.stderr
    migrate('upgrade','e922_admin_avatar')
    with closing(sqlite3.connect(database)) as db:
        fields=[row for row in db.execute('PRAGMA table_info(agents)') if row[1]!='id' and row[3] and row[4] is None]
        values={row[1]:0 if row[2].upper()=='INTEGER' else '2040-01-01' if row[1] in ('created_at','updated_at') else '' for row in fields};values['name']='fixture'
        db.execute('INSERT INTO agents ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',list(values.values()));db.commit()
    migrate('upgrade','head')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('e923_agent_analysis',)
        db.execute("INSERT INTO agent_analysis_config(agent_id,created_at,updated_at) VALUES (1,'2040-01-01','2040-01-01')");db.commit()
        assert db.execute('SELECT buckets FROM agent_analysis_config').fetchone()==('{}',)
        db.execute('UPDATE agent_analysis_config SET buckets=?',('{"coin":[],"success":[],"apps":[]}',));db.commit()
    migrate('upgrade','head')
    migrate('downgrade','e922_admin_avatar')
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT name FROM agents').fetchone()==('fixture',)
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='agent_analysis_config'").fetchone()
    migrate('upgrade','head')
    with closing(sqlite3.connect(database)) as db:assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
print('Analysis settings: full migration chain, defaults, downgrade, existing agent preservation and re-upgrade passed')
