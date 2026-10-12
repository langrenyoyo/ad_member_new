"""Wallet precision and migration checks against disposable databases."""
import importlib.util
from pathlib import Path
from decimal import Decimal
import unittest
from unittest.mock import patch
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
import test_member_policy as fixtures
from app import main_from_txt as m


class WalletDecimalTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown

    def test_orphan_records_fail_even_without_members(self):
        from app.wallet_audit import reconcile
        with self.factory() as s:
            s.query(m.Member).delete()
            s.add(m.CoinLog(user_id=999,agent_id=1,game_id=1,coin_before=0,coin=1,coin_after=2,type=1))
            s.add(m.payouts.Payout(withdrawal_id=999,member_id=999,request_key='orphan',game_id=1,
                amount_cents=100,coin_cost=5,account='test',real_name='test',out_biz_no='orphan',state='invalid'))
            s.commit()
            report=reconcile(s)
            self.assertFalse(report['passed'])
            self.assertEqual({x['kind'] for x in report['findings']},
                {'orphan_ledger','ledger_equation','orphan_payout','missing_withdrawal','unknown_payout_state'})

    def test_reconciliation_detects_ledger_and_freeze_mismatch_without_writing(self):
        from app.wallet_audit import reconcile
        with self.factory() as s:
            self.assertTrue(reconcile(s)['passed'])
            user=s.get(m.Member,1);user.coin=Decimal('12');user.freeze_coin=Decimal('3')
            s.add(m.CoinLog(user_id=1,agent_id=1,game_id=1,coin_before=0,coin=10,coin_after=11,type=1))
            s.commit()
            report=reconcile(s)
            self.assertEqual({f['kind'] for f in report['findings']},
                {'ledger_equation','wallet_vs_latest_log','frozen_vs_payouts'})
            self.assertEqual(s.get(m.Member,1).coin,12)
            self.assertFalse(s.dirty)

    def test_reward_ledger_without_credit_is_reported(self):
        from app.wallet_audit import reconcile
        with self.factory() as s:
            s.add(m.AppAdSession(id='ledger-ad',member_id=1,agent_id=1,game_id=1,request_id='ledger-request',
                status='rewarded',coin_log_id=None,session_token_hash='x',expires_at=m.now()))
            s.add(m.AppAdEvent(event_id='policy:ledger-ad',ad_session_id='ledger-ad',member_id=1,
                event_type='policy_snapshot',result_json='{}'))
            s.add(m.member_policy.RewardLedger(ad_session_id='ledger-ad',member_id=1,beneficiary_id=1,
                game_id=1,kind='reward',amount=Decimal('1'),rule_json='{}'))
            s.commit()
            report=reconcile(s)
            self.assertTrue(any(x['kind']=='reward_missing_credit' for x in report['findings']))

    def test_invalid_snapshot_does_not_abort_remaining_audit(self):
        from app.wallet_audit import reconcile
        with self.factory() as s:
            invalid = ['[]', 'null', '42', '"text"', '{broken', '{"rule": []}']
            for index, payload in enumerate(invalid):
                aid = f'invalid-snapshot-{index}'
                s.add(m.AppAdSession(id=aid,member_id=1,agent_id=1,game_id=1,request_id=aid,
                    status='rewarded',session_token_hash='x',expires_at=m.now()))
                s.add(m.AppAdEvent(event_id='policy:'+aid,ad_session_id=aid,member_id=1,
                    event_type='policy_snapshot',result_json=payload))
            s.add(m.CoinLog(user_id=2,agent_id=1,game_id=1,coin_before=0,coin=1,coin_after=2,type=1))
            s.commit()
            report = reconcile(s)
            self.assertFalse(report['passed'])
            errors = [f for f in report['findings'] if f['kind']=='invalid_settlement_snapshot']
            self.assertEqual(len(errors), len(invalid))
            self.assertTrue(any(f['kind']=='ledger_equation' for f in report['findings']))
            self.assertFalse(s.dirty)

    def test_commission_credit_cannot_be_reused_or_assigned_to_wrong_member(self):
        from app.wallet_audit import reconcile
        with self.factory() as s:
            log=m.CoinLog(user_id=1,agent_id=1,game_id=1,coin_before=0,coin=1,coin_after=1,type=301)
            s.add(log);s.flush()
            for index in range(2):
                s.add(m.member_policy.RewardLedger(ad_session_id=f'absent-{index}',member_id=1,
                    beneficiary_id=2,game_id=1,kind='commission_1',amount=1,coin_log_id=log.id,rule_json='{}'))
            s.commit()
            kinds={x['kind'] for x in reconcile(s)['findings']}
            self.assertTrue({'reward_missing_ad','reward_credit_mismatch','reward_reused_credit'} <= kinds)

    def test_malformed_commission_outcomes_are_reported_without_aborting(self):
        import json
        from app.wallet_audit import reconcile
        invalid = [[], {'commission_audit_version':1}, {'commission_outcomes':None},
            {'commission_outcomes':[None]}, {'commission_outcomes':[{}]},
            {'commission_outcomes':[{'eligible':True,'beneficiary_id':2,'level':1,'amount':'NaN'}]},
            {'commission_outcomes':[{'eligible':True,'beneficiary_id':2,'level':1,'amount':'Infinity'}]}]
        with self.factory() as s:
            for index, snapshot in enumerate(invalid):
                s.add(m.member_policy.RewardLedger(ad_session_id=f'bad-outcome-{index}',member_id=1,
                    beneficiary_id=1,game_id=1,kind='reward',amount=1,rule_json=json.dumps(snapshot)))
            s.commit()
            report = reconcile(s)
            errors = [f for f in report['findings'] if f['kind']=='invalid_commission_outcomes']
            self.assertEqual(len(errors), len(invalid))
            self.assertFalse(report['passed'])
            self.assertFalse(s.dirty)

    def test_unchanged_decimal_balance_can_accompany_profile_edit(self):
        headers=fixtures.MemberPolicyTests.admin_headers(self)
        with self.factory() as s:
            s.get(m.Member,1).coin=Decimal('.1');s.commit()
        response=self.client.patch('/api/v1/members/1',headers=headers,json={'coin':0.1,'name':'profile'})
        self.assertEqual(response.status_code,200,response.text)
        response=self.client.patch('/api/v1/members/1',headers=headers,json={'coin':0.2})
        self.assertEqual(response.status_code,409)

    def test_repeated_credit_and_log_are_exact(self):
        with self.factory() as s:
            user=s.get(m.Member,1)
            for _ in range(10):
                before=m.coin_amount(user.coin)
                user.coin=before+Decimal('.1')
                s.add(m.CoinLog(user_id=1,agent_id=1,game_id=1,coin_before=before,
                    coin=Decimal('.1'),coin_after=user.coin,type=1))
                s.flush();s.refresh(user)
            self.assertIsInstance(user.coin,Decimal)
            self.assertEqual(user.coin,Decimal('1.000000'))
            logs=s.scalars(sa.select(m.CoinLog).order_by(m.CoinLog.id)).all()
            self.assertTrue(all(r.coin_before+r.coin==r.coin_after for r in logs))
            self.assertEqual(sum(r.coin for r in logs),user.coin)
        self.assertEqual(m.coin_amount('0.1234569'),Decimal('0.123456'))

    def test_migration_archives_originals_and_converts_types(self):
        path=Path(__file__).resolve().parents[1]/'alembic/versions/e932_wallet_decimal.py'
        spec=importlib.util.spec_from_file_location('wallet_migration',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        engine=sa.create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                for table,columns in migration.TABLES.items():
                    connection.execute(sa.text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, '+', '.join(f'{c} FLOAT NOT NULL' for c in columns)+')'))
                    connection.execute(sa.text(f'INSERT INTO {table} VALUES (1, '+', '.join('0.1234569' for c in columns)+')'))
                with patch.object(migration,'op',Operations(MigrationContext.configure(connection))):migration.upgrade()
                count=connection.scalar(sa.text('SELECT COUNT(*) FROM wallet_decimal_migration_values'))
                self.assertEqual(count,9)
                for table,columns in migration.TABLES.items():
                    schema={c['name']:c['type'] for c in sa.inspect(connection).get_columns(table)}
                    for column in columns:
                        self.assertIsInstance(schema[column],sa.Numeric)
                        self.assertEqual(Decimal(str(connection.scalar(sa.text(f'SELECT {column} FROM {table}')))),Decimal('.123456'))
        finally:engine.dispose()
