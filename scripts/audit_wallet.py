"""Run against a backup/copy via DATABASE_URL. No writes to the business database."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import main_from_txt as m
from app.wallet_audit import reconcile
from sqlalchemy import text

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='Local JSON report path')
    args = parser.parse_args()
    with m.SessionLocal() as session:
        if session.get_bind().dialect.name == 'postgresql':
            session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        elif session.get_bind().dialect.name == 'sqlite':
            session.execute(text('PRAGMA query_only = ON'))
            session.execute(text('BEGIN'))
        else:
            raise RuntimeError('Only PostgreSQL and SQLite are supported')
        report = reconcile(session)
        session.rollback()
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"members={report['member_count']} findings={len(report['findings'])} migration_changed_fields={report['migration_changed_fields']}")
    sys.exit(0 if report['passed'] else 2)
