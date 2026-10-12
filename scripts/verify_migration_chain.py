"""Upgrade an isolated empty SQLite database and check model table/column coverage."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.main_from_txt import Base

with tempfile.TemporaryDirectory() as temporary:
    url = 'sqlite:///' + (Path(temporary) / 'migration.sqlite').as_posix()
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT,
        env=dict(os.environ, DATABASE_URL=url), capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        existing = set(inspector.get_table_names())
        assert set(Base.metadata.tables) <= existing
        for name, table in Base.metadata.tables.items():
            assert set(table.columns.keys()) <= {c['name'] for c in inspector.get_columns(name)}, name
    finally:
        engine.dispose()
print('Empty-database migration chain and model coverage passed (SQLite).')
