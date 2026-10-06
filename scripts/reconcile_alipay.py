"""One reconciliation pass. Schedule every minute; --execute also sends queued orders."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import or_, select
from app import main_from_txt as m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Send approved queued transfers as well as querying pending ones')
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    m.require_payment_integration()
    p = m.payouts
    states = ['processing', 'queued'] if args.execute else ['processing']
    with m.SessionLocal() as session:
        rows = session.execute(select(p.Payout.withdrawal_id, p.Payout.state).where(p.Payout.state.in_(states),
            or_(p.Payout.next_query_at.is_(None), p.Payout.next_query_at <= m.now()))
            .order_by(p.Payout.id).limit(min(100, max(1, args.limit)))).all()
    failures = 0
    for wid, state in rows:
        try:
            result = p.transfer(wid, None, query_only=state != 'queued')
            print(wid, result['payout']['state'])
        except Exception:
            failures += 1
            print(wid, 'reconcile_error', file=sys.stderr)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
