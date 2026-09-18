"""Exercise both deployed e916 shapes and e917, never a business database."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECOND = ('raffle_num2', 'star_countdown2', 'over_countdown2')

for revision, missing in [('e916_member_lottery_download', True), ('e917_member_password_hashes', True), ('e917_member_password_hashes', False)]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'migration.db'
        env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + path.as_posix(), 'APP_ENV': 'development'}
        def migrate(action, target):
            subprocess.run([sys.executable, '-m', 'alembic', action, target], cwd=ROOT,
                           env=env, check=True, capture_output=True, text=True)
        migrate('upgrade', revision)
        with closing(sqlite3.connect(path)) as db:
            if missing:
                for name in SECOND:
                    db.execute('ALTER TABLE members DROP COLUMN ' + name)
            columns = db.execute('PRAGMA table_info(members)').fetchall()
            values = {name: (0 if 'INT' in kind.upper() or 'FLOAT' in kind.upper() else '')
                      for _, name, kind, required, default, pk in columns if required and default is None and not pk}
            values.update(username='legacy-fixture', real_name='preserved', down_load=None, raffle_num=12,
                          created_at='2026-09-16 00:00:00', updated_at='2026-09-16 00:00:00')
            if not missing:
                values.update(raffle_num2=7, star_countdown2=1.25, over_countdown2=8.75)
            keys = list(values)
            db.execute('INSERT INTO members (' + ','.join(keys) + ') VALUES (' + ','.join('?' for _ in keys) + ')', [values[k] for k in keys])
            values.update(username='nonempty-download', down_load='https://example.test/app.apk')
            db.execute('INSERT INTO members (' + ','.join(keys) + ') VALUES (' + ','.join('?' for _ in keys) + ')', [values[k] for k in keys])
            db.commit()
        migrate('upgrade', 'head')
        with closing(sqlite3.connect(path)) as db:
            columns = {row[1]: row for row in db.execute('PRAGMA table_info(members)')}
            assert all(name in columns for name in SECOND)
            assert columns['down_load'][3] == 1
            row = db.execute('SELECT real_name,raffle_num,down_load,raffle_num2,star_countdown2,over_countdown2 FROM members WHERE username=?', ('legacy-fixture',)).fetchone()
            assert row == ('preserved',12,'',*((None,None,None) if missing else (7,1.25,8.75))), row
            assert db.execute('SELECT down_load FROM members WHERE username=?', ('nonempty-download',)).fetchone() == ('https://example.test/app.apk',)
            try:
                db.execute('UPDATE members SET down_load=NULL')
            except sqlite3.IntegrityError:
                db.rollback()
            else:
                raise AssertionError('NULL download accepted')
            db.execute('UPDATE members SET raffle_num2=9,star_countdown2=2.5,over_countdown2=8.5')
            db.commit()
        migrate('upgrade', 'head')
        migrate('downgrade', 'e917_member_password_hashes')
        migrate('upgrade', 'head')
        with closing(sqlite3.connect(path)) as db:
            assert db.execute('SELECT raffle_num2,star_countdown2,over_countdown2 FROM members').fetchall() == [(9,2.5,8.5)]*2
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        print(f'{revision}, missing_second_fields={missing}: repair, preservation, repeat and downgrade/re-upgrade passed')
