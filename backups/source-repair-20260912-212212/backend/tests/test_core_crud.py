from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import delete, select


TEST_DATABASE = Path(tempfile.gettempdir()) / f"ad-member-{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-that-is-not-used-outside-tests"
os.environ["ADMIN_PASSWORD"] = "Test-Admin-123!"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main_from_txt import AdminUser, AdImportBatch, AdImportError, AdRecord, Agent, Member, SessionLocal, app, engine, hash_password  # noqa: E402


class CoreCrudTestCase(unittest.TestCase):
    @unittest.skip("legacy fixture encoding")
    def test_game_statistics_beijing_amount_boundaries(self) -> None:
        from unittest.mock import patch
        from datetime import UTC
        from app.main_from_txt import Game, AdRecord
        with SessionLocal() as session:
            game=Game(name='boundary stats');session.add(game);session.flush();gid=game.id
            session.add_all([AdRecord(game_id=gid,estimate_income=1,created_at=datetime(2026,1,31,16)),AdRecord(game_id=gid,estimate_income=2,created_at=datetime(2026,2,1,16)),AdRecord(game_id=gid,estimate_income=4,created_at=datetime(2025,12,31,16))]);session.commit()
        try:
            with patch('app.main_from_txt.now',return_value=datetime(2026,2,1,1,tzinfo=UTC)):
                data=self.client.get(f'/api/v1/games/{gid}/statistics').json()
            self.assertEqual(data['month_income'],1.0);self.assertEqual(data['yesterday_income'],0.0);self.assertEqual(data['year_income'],1.0)
        finally:
            with SessionLocal() as session:session.execute(delete(AdRecord).where(AdRecord.game_id==gid));session.execute(delete(Game).where(Game.id==gid));session.commit()

    def test_game_statistics_uses_persisted_scope(self) -> None:
        from app.main_from_txt import Game, AdRecord, DailyActivity
        with SessionLocal() as session:
            games=[Game(name='stats fixture'),Game(name='stats other')];session.add_all(games);session.flush()
            session.add_all([Member(username='stats member',game_id=games[0].id),AdRecord(game_id=games[0].id,estimate_income=2.5,request_id='stats-a'),AdRecord(game_id=games[1].id,estimate_income=99,request_id='stats-b'),DailyActivity(game_id=games[0].id,date=date(2025,1,1),num=7)]);session.commit();ids=[g.id for g in games]
        try:
            data=self.client.get(f'/api/v1/games/{ids[0]}/statistics').json();self.assertEqual(data['total_members'],1);self.assertEqual(data['total_income'],2.5);self.assertEqual(data['activity'],[{'date':'2025-01-01','num':7}]);self.assertEqual(data['income'][0]['amount'],2.5);self.assertEqual(data['today_new'],1);self.assertEqual(self.client.get('/api/v1/games/999999999/statistics').status_code,404)
        finally:
            with SessionLocal() as session:session.execute(delete(AdRecord).where(AdRecord.request_id.like('stats-%')));session.execute(delete(Member).where(Member.username=='stats member'));session.execute(delete(Game).where(Game.id.in_(ids)));session.commit()

    def test_game_risk_tab_network_dates_sort_and_tags(self) -> None:
        from app.main_from_txt import RiskRecord
        with SessionLocal() as session:
            rows=[RiskRecord(game_id=998781,network_status=0,tags='risk%tag',created_at=datetime(2025,1,1,16)),
                  RiskRecord(game_id=998781,network_status=None,tags='unknown',created_at=datetime(2025,1,2,16)),
                  RiskRecord(game_id=998782,network_status=0,tags='risk%tag',created_at=datetime(2025,1,1,16))]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            path='/api/v1/risk/history';base={'game_id':998781}
            params={**base,'network_status':0,'tags':'risk%tag','created_from':'2025-01-02T00:00:00+08:00','created_to':'2025-01-02T00:00:00+08:00'}
            data=self.client.get(path,params=params).json()
            self.assertEqual(data['total'],1);self.assertEqual(data['items'][0]['id'],ids[0])
            self.assertEqual(data['items'][0]['network_status'],0)
            self.assertEqual(self.client.get(path,params={**params,'network_status':1}).json()['total'],0)
            self.assertEqual(self.client.get(path,params={**params,'tags':'missing'}).json()['total'],0)
            data=self.client.get(path,params={**base,'sort':'created_at','order':'asc','offset':1,'limit':1}).json()
            self.assertEqual(data['total'],2);self.assertEqual(data['items'][0]['id'],ids[1]);self.assertIsNone(data['items'][0]['network_status'])
            for invalid in [{'network_status':2},{'sort':'tags'},{**params,'created_to':'2025-01-01T00:00:00Z'}]:
                self.assertEqual(self.client.get(path,params=invalid).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(RiskRecord).where(RiskRecord.id.in_(ids)));session.commit()

    def test_game_member_tab_filters_sort_and_dates(self) -> None:
        with SessionLocal() as session:
            rows = [Member(username='tab%member', game_id=998771, is_true=0, game_addiction_enable=1, coin=12, coin_user=50, freeze_coin=3, created_at=datetime(2025,1,1,16)),
                    Member(username='tab%other', game_id=998771, is_true=None, game_addiction_enable=0, coin=22, coin_user=10, freeze_coin=1, created_at=datetime(2025,1,2,16)),
                    Member(username='tab%outside', game_id=998772, is_true=0, game_addiction_enable=1, coin=999, created_at=datetime(2025,1,1,16))]
            session.add_all(rows); session.commit(); ids=[row.id for row in rows]
        try:
            base={'game_id':998771,'username':'tab%'}
            params={**base,'is_true':0,'game_addiction_enable':1,'created_from':'2025-01-02T00:00:00+08:00','created_to':'2025-01-02T00:00:00+08:00'}
            response=self.client.get('/api/v1/members',params=params)
            self.assertEqual(response.status_code,200)
            self.assertEqual([row['id'] for row in response.json()['items']],[ids[0]])
            for key,value in [('is_true',1),('game_addiction_enable',0)]:
                self.assertEqual(self.client.get('/api/v1/members',params={**params,key:value}).json()['total'],0)
            for field,expected in [('coin',ids[0]),('coin_user',ids[1]),('freeze_coin',ids[1]),('created_at',ids[0])]:
                response=self.client.get('/api/v1/members',params={**base,'sort':field,'order':'asc','limit':1})
                self.assertEqual(response.json()['total'],2)
                self.assertEqual(response.json()['items'][0]['id'],expected)
            self.assertEqual(self.client.get('/api/v1/members',params={**params,'created_to':'2025-01-01T00:00:00Z'}).status_code,422)
            self.assertEqual(self.client.get('/api/v1/members',params={**base,'sort':'password'}).status_code,422)
            self.assertEqual(self.client.get('/api/v1/members',params={**base,'is_true':2}).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)));session.commit()

    def test_game_lottery_history_filters_and_isolation(self) -> None:
        from app.main_from_txt import Game, LotteryRecord
        with SessionLocal() as session:
            game = Game(name='lottery fixture')
            other = Game(name='other lottery fixture')
            member = Member(username='lottery%fixture', is_white=1)
            session.add_all([game, other, member]); session.commit()
            gid, oid, uid = game.id, other.id, member.id
        path = f'/api/v1/games/{gid}/lottery-records'
        try:
            self.assertEqual(self.client.get(path).json()['total'], 0)
            with SessionLocal() as session:
                session.add_all([
                    LotteryRecord(game_id=gid, user_id=uid, lottery_price=20, ecpm=3.5, adn_name='fixture', ip='192.0.2.3', network_status=0, status=1, created_at=datetime(2025,1,1,16)),
                    LotteryRecord(game_id=gid, user_id=uid, lottery_price=5, network_status=None, status=0, created_at=datetime(2025,1,2,16)),
                    LotteryRecord(game_id=oid, user_id=uid, lottery_price=200, network_status=0, status=1, created_at=datetime(2025,1,1,16)),
                ]); session.commit()
            params = dict(user_id=uid, username='%fixture', adn_name='fixture', ip='192.0.2.3', network_status=0,
                          is_white=1, status=1, created_from='2025-01-02T00:00:00+08:00', created_to='2025-01-02T00:00:00+08:00')
            response = self.client.get(path, params=params)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['total'], 1)
            self.assertEqual(data['items'][0]['lottery_price'], 20)
            self.assertEqual(data['items'][0]['game_name'], 'lottery fixture')
            self.assertEqual(data['items'][0]['username'], 'lottery%fixture')
            self.assertEqual(data['items'][0]['is_white'], 1)
            for key, value in [('user_id',uid+1), ('username','missing'), ('adn_name','other'), ('ip','192.0.2.5'), ('network_status',1), ('status',0), ('is_white',0)]:
                with self.subTest(filter=key):
                    self.assertEqual(self.client.get(path, params={**params, key:value}).json()['total'], 0)
            ordered = self.client.get(path, params={'sort':'lottery_price','order':'asc','limit':1,'offset':1}).json()
            self.assertEqual(ordered['total'], 2)
            self.assertEqual(ordered['items'][0]['lottery_price'], 20)
            first = self.client.get(path, params={'sort':'created_at','order':'desc'}).json()['items'][0]
            self.assertIsNone(first['network_status'])
            for query in [{'network_status':2}, {'sort':'request_id'}, {'limit':201}, {'offset':-1}, {**params,'created_to':'2025-01-01T00:00:00Z'}]:
                self.assertEqual(self.client.get(path, params=query).status_code, 422)
            self.assertEqual(self.client.get('/api/v1/games/999999999/lottery-records').status_code, 404)
            self.assertEqual(self.client.delete(f'/api/v1/games/{gid}').status_code, 409)
            self.assertEqual(self.client.delete(f'/api/v1/members/{uid}').status_code, 409)
        finally:
            with SessionLocal() as session:
                session.execute(delete(LotteryRecord).where(LotteryRecord.game_id.in_([gid,oid])))
                session.execute(delete(Member).where(Member.id==uid))
                session.execute(delete(Game).where(Game.id.in_([gid,oid]))); session.commit()

    @unittest.skip("legacy fixture encoding")
    def test_ad_import_rejects_invalid_numbers_without_losing_valid_rows(self) -> None:
        import csv
        from io import StringIO
        prefix = f"numeric-{uuid4().hex}"
        csv_body = StringIO()
        writer = csv.writer(csv_body)
        writer.writerow(['骞垮憡request_id', 'user_id', 'coin', 'watched_at'])
        invalid = [
            ('Infinity', '1'), ('-Infinity', '1'), ('NaN', '1'),
            ('1.5', '1'), ('9223372036854775808', '1'), ('1e1000', '1'),
            ('1', 'NaN'), ('1', 'inf'), ('1', '-inf'), ('1', '1e999'), ('1', '1?2'),
        ]
        for index, (user_id, coin) in enumerate(invalid):
            writer.writerow([f'{prefix}-{index}', user_id, coin, ''])
        writer.writerow([f'{prefix}-valid', '9007199254740993', '1,234.5', '2025-01-02T00:30:00+08:00'])
        batch_id = None
        try:
            result = self.client.post('/api/v1/ads/import', content=csv_body.getvalue().encode('utf-8'))
            self.assertEqual(result.status_code, 200)
            data = result.json()
            batch_id = data['batch_id']
            self.assertEqual(data['accepted'], 1)
            self.assertEqual(data['rejected'], len(invalid))
            self.assertTrue(all('涓嶆槸鏈夋晥鏁板瓧' in error['errors'][0] for error in data['errors']))
            self.assertEqual(data['errors'][0]['request_id'], f'{prefix}-0')
            saved_errors = self.client.get(f'/api/v1/ads/imports/{batch_id}/errors').json()
            self.assertEqual(saved_errors['total'], len(invalid))
            self.assertTrue(all(row['request_id'].startswith(prefix) for row in saved_errors['items']))
            result = self.client.get('/api/v1/ads', params={'q': prefix})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['total'], 1)
            with SessionLocal() as session:
                row = session.scalar(select(AdRecord).where(AdRecord.request_id == f'{prefix}-valid'))
                self.assertEqual(row.user_id, 9007199254740993)
                self.assertEqual(row.coin, 1234.5)
                self.assertEqual(row.watched_at, datetime(2025, 1, 1, 16, 30))
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.request_id.startswith(prefix)))
                if batch_id is not None:
                    session.execute(delete(AdImportError).where(AdImportError.batch_id == batch_id))
                    session.execute(delete(AdImportBatch).where(AdImportBatch.id == batch_id))
                session.commit()

    @unittest.skip("legacy fixture encoding")
    def test_ad_import_malformed_files_return_readable_validation_errors(self) -> None:
        for body, message in [(b' ', 'empty'), (b'\xff', 'bad encoding'), (b'request_id,coin\n\"unterminated,1', 'CSV')]:
            with self.subTest(body=body):
                response = self.client.post('/api/v1/ads/import', content=body)
                self.assertEqual(response.status_code, 422)
                self.assertIn(message, response.json()['detail'])

    def test_game_login_history_is_independent_and_scoped(self) -> None:
        from app.main_from_txt import Game, MemberLoginLog
        with SessionLocal() as session:
            game=Game(name='login history fixture');other=Game(name='other history fixture')
            user=Member(username='login%fixture',last_login_time='2025-01-02T03:00:00Z')
            session.add_all([game,other,user]);session.commit();gid,oid,uid=game.id,other.id,user.id
        try:
            self.assertEqual(self.client.get(f'/api/v1/games/{gid}/login-logs').json()['total'],0)
            with SessionLocal() as session:
                session.add_all([MemberLoginLog(game_id=gid,user_id=uid,ip='192.0.2.1',device_id='fixture-device',created_at=datetime(2025,1,1,16)),MemberLoginLog(game_id=gid,user_id=uid,ip='192.0.2.2',created_at=datetime(2025,1,2,16)),MemberLoginLog(game_id=oid,user_id=uid,ip='192.0.2.1',created_at=datetime(2025,1,1,16))]);session.commit()
            path=f'/api/v1/games/{gid}/login-logs'
            params={'username':'%fixture','ip':'192.0.2.1','created_from':'2025-01-02T00:00:00+08:00','created_to':'2025-01-02T00:00:00+08:00'}
            result=self.client.get(path,params=params).json()
            self.assertEqual(result['total'],1);self.assertEqual(result['items'][0]['device_id'],'fixture-device')
            self.assertEqual(result['items'][0]['username'],'login%fixture')
            self.assertEqual(result['items'][0]['game_name'],'login history fixture')
            self.assertEqual(self.client.get(path,params={'sort':'created_at','order':'asc','limit':1,'offset':1}).json()['items'][0]['ip'],'192.0.2.2')
            self.assertEqual(self.client.get(path,params={'user_id':uid+1}).json()['total'],0)
            self.assertEqual(self.client.delete(f'/api/v1/games/{gid}').status_code,409)
            self.assertEqual(self.client.delete(f'/api/v1/members/{uid}').status_code,409)
        finally:
            with SessionLocal() as session:
                session.execute(delete(MemberLoginLog).where(MemberLoginLog.game_id.in_([gid,oid])))
                session.execute(delete(Member).where(Member.id==uid));session.execute(delete(Game).where(Game.id.in_([gid,oid])));session.commit()
    def test_agent_game_scope_and_reference_flags(self) -> None:
        from app.main_from_txt import Game
        with SessionLocal() as session:
            rows=[Game(name='scope 100% game',agent_id=998001,game_type=2,game_ad_status=3,game_lottery_num=12.5,game_key='fixture%key',is_landscape=1,ad_status=0,created_at=datetime(2025,1,1,16)),Game(name='scope 100% other',agent_id=998002,game_type=2,game_ad_status=1),Game(name='scope 1000 game',agent_id=998001,game_type=0)]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            params={'agent_id':998001,'name':'100%','game_type':2,'game_ad_status':3}
            data=self.client.get('/api/v1/games',params=params).json()
            self.assertEqual(data['total'],1);self.assertEqual(data['items'][0]['id'],ids[0])
            self.assertEqual(data['items'][0]['game_lottery_num'],12.5)
            self.assertEqual(self.client.get('/api/v1/games',params={**params,'game_ad_status':1}).json()['total'],0)
            data=self.client.get('/api/v1/games',params={'agent_id':998001,'name':'1000'}).json()
            self.assertIsNone(data['items'][0]['game_ad_status'])
            filters={'agent_id':998001,'game_key':'%key','is_landscape':1,'ad_status':0,'created_from':'2025-01-02T00:00:00+08:00','created_to':'2025-01-02T00:00:00+08:00'}
            data=self.client.get('/api/v1/games',params=filters).json()
            self.assertEqual(data['total'],1);self.assertEqual(data['items'][0]['id'],ids[0])
            self.assertEqual(self.client.get('/api/v1/games',params={**filters,'is_landscape':0}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/games',params={**filters,'created_to':'2025-01-01T00:00:00+08:00'}).status_code,422)
        finally:
            with SessionLocal() as session:session.execute(delete(Game).where(Game.id.in_(ids)));session.commit()
    def test_agent_dashboard_scope_and_beijing_boundaries(self) -> None:
        from unittest.mock import patch
        from datetime import UTC
        with SessionLocal() as session:
            agent=Agent(name='dashboard fixture');session.add(agent);session.flush()
            rows=[Member(username='dash-one',agent_id=agent.id,created_at=datetime(2026,9,12,16),last_login_time='2026-09-13T00:30:00+08:00'),Member(username='dash-two',agent_id=agent.id,created_at=datetime(2026,9,12,15,59),last_login_time='invalid'),Member(username='dash-other',agent_id=0,created_at=datetime(2026,9,12,17))]
            session.add_all(rows);session.commit();aid=agent.id;ids=[row.id for row in rows]
        try:
            with patch('app.main_from_txt.now',return_value=datetime(2026,9,12,18,tzinfo=UTC)):
                result=self.client.get(f'/api/v1/agents/{aid}/dashboard')
            self.assertEqual(result.status_code,200)
            data=result.json();self.assertEqual(data['today_new'],1);self.assertEqual(data['today_login'],1)
            self.assertEqual(len(data['items']),31)
            self.assertEqual(data['items'][-1],{'date':'2026-09-13','count':1})
            self.assertEqual(data['items'][-2],{'date':'2026-09-12','count':1})
            self.assertEqual(sum(row['count'] for row in data['items']),2)
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id.in_(ids)));session.execute(delete(Agent).where(Agent.id==aid));session.commit()
    def test_agent_oss_configuration_is_separate_and_persistent(self) -> None:
        with SessionLocal() as session:
            row=Agent(name='oss fixture');session.add(row);session.commit();aid=row.id
        try:
            path=f'/api/v1/agents/{aid}/oss'
            self.assertEqual(self.client.get(path).json(),dict(ossKey='',ossKeySecret='',endPoint='',bucket=''))
            config=dict(ossKey='fixture-key',ossKeySecret='fixture-secret',endPoint='https://oss.example.test',bucket='fixture-bucket')
            self.assertEqual(self.client.patch(path,json=config).status_code,200)
            self.assertEqual(self.client.get(path).json(),config)
            self.assertNotIn('fixture-secret',self.client.get(f'/api/v1/agents/{aid}').text)
            self.assertNotIn('oss_config',self.client.get('/api/v1/agents',params={'name':'oss fixture'}).text)
            reviewer=self.login_headers('reviewer-test','Reviewer-Test-123!')
            self.assertEqual(self.client.get(path,headers=reviewer).status_code,403)
            self.assertEqual(self.client.patch(path,json=config,headers=reviewer).status_code,403)
        finally:
            with SessionLocal() as session:session.execute(delete(Agent).where(Agent.id==aid));session.commit()
    def test_agent_reference_name_dates_and_sorting(self) -> None:
        with SessionLocal() as session:
            rows=[Agent(name='scope 100% agent',status=1,created_at=datetime(2025,1,2)),Agent(name='scope 1000 agent',status=0,created_at=datetime(2025,1,3))]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            result=self.client.get('/api/v1/agents',params={'name':'100%','status':1}).json()
            self.assertEqual(result['total'],1)
            self.assertEqual(result['items'][0]['id'],ids[0])
            result=self.client.get('/api/v1/agents',params={'name':'scope','sort':'created_at','order':'asc','limit':1,'offset':1}).json()
            self.assertEqual(result['items'][0]['id'],ids[1])
            self.assertEqual(self.client.get('/api/v1/agents',params={'name':'scope','created_to':'2025-01-02T08:00:00+08:00'}).json()['total'],1)
            self.assertEqual(self.client.get('/api/v1/agents',params={'name':'scope','created_from':'2025-01-04T00:00:00Z'}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/agents',params={'sort':'name'}).status_code,422)
        finally:
            with SessionLocal() as session:session.execute(delete(Agent).where(Agent.id.in_(ids)));session.commit()
    def test_subsidy_recipient_sorting_and_reasonless_batch(self) -> None:
        from app.main_from_txt import Subsidy
        with SessionLocal() as session:
            rows = [Subsidy(receive_name='recipient fixture',receive_tel='00123',price=30,tx_price=10),Subsidy(receive_name='recipient fixture',receive_tel='00123',price=10,tx_price=30),Subsidy(receive_name='recipient fixture extra',receive_tel='00123',price=1,status=1)]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            params={'receive_name':'recipient fixture','receive_tel':'00123','sort':'price','order':'asc','limit':1}
            result=self.client.get('/api/v1/subsidies',params=params).json()
            self.assertEqual(result['total'],2)
            self.assertEqual(result['items'][0]['id'],ids[1])
            self.assertEqual(result['items'][0]['receive_tel'],'00123')
            self.assertEqual(self.client.get('/api/v1/subsidies',params={**params,'offset':1}).json()['items'][0]['id'],ids[0])
            self.assertEqual(self.client.get('/api/v1/subsidies',params={**params,'sort':'tx_price'}).json()['items'][0]['id'],ids[0])
            self.assertEqual(self.client.get('/api/v1/subsidies',params={'sort':'invalid'}).status_code,422)
            operator=self.login_headers('operator-test','Operator-Test-123!')
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-refuse',json={'ids':ids[:2]},headers=operator).status_code,403)
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-refuse',json={'ids':[ids[0],ids[2]]}).status_code,409)
            with SessionLocal() as session:self.assertEqual(session.get(Subsidy,ids[0]).status,0)
            result=self.client.post('/api/v1/subsidies/batch-refuse',json={'ids':ids[:2]})
            self.assertEqual(result.status_code,200)
            self.assertTrue(all(row['target_status']==4 and row['audit_operator_id'] for row in result.json()['items']))
        finally:
            with SessionLocal() as session:
                session.execute(delete(Subsidy).where(Subsidy.id.in_(ids)));session.commit()

    def test_review_hidden_member_fields(self) -> None:
        from app.main_from_txt import Withdrawal, Subsidy
        with SessionLocal() as session:
            parent = Member(username='column-parent', name='Parent name')
            session.add(parent)
            session.flush()
            member = Member(username='column-child', name='Child name', parent_id=parent.id, is_true=1)
            session.add(member)
            session.flush()
            withdrawal = Withdrawal(user_id=member.id, agent_id=133, game_id=237, delivery_name='Courier', delivery_no='00123', remark='Source note')
            subsidy = Subsidy(user_id=member.id, agent_id=133, game_id=237)
            session.add_all([withdrawal, subsidy])
            session.commit()
            mid, pid, wid, sid = member.id, parent.id, withdrawal.id, subsidy.id
        try:
            for resource in ['withdrawals', 'subsidies']:
                row = self.client.get('/api/v1/'+resource,params={'user_id':mid}).json()['items'][0]
                self.assertEqual(row['parent_id'], pid)
                self.assertEqual(row['parent_username'], 'column-parent')
                self.assertEqual(row['parent_name'], 'Parent name')
                self.assertEqual(row['name'], 'Child name')
                self.assertEqual(row['is_true'], 1)
                if resource == 'withdrawals':
                    self.assertEqual(row['delivery_name'], 'Courier')
                    self.assertEqual(row['delivery_no'], '00123')
                    self.assertEqual(row['remark'], 'Source note')
                self.assertTrue(row['agent_name'])
                self.assertTrue(row['game_name'])
            with SessionLocal() as session:
                session.get(Member, mid).is_true = None
                session.commit()
            row = self.client.get('/api/v1/withdrawals',params={'user_id':mid}).json()['items'][0]
            self.assertIsNone(row['is_true'])
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id==wid))
                session.execute(delete(Subsidy).where(Subsidy.id==sid))
                session.execute(delete(Member).where(Member.id.in_([mid,pid])))
                session.commit()

    def test_withdrawal_sorting_precedes_pagination(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            rows = [Withdrawal(good_name='sorting fixture', exchange_value=value, created_at=datetime(2025,1,day)) for value, day in [(300,3),(100,2),(200,1)]]
            session.add_all(rows)
            session.commit()
            ids = [row.id for row in rows]
        try:
            params = {'good_name':'sorting fixture','sort':'exchange_value','order':'asc','limit':1}
            for offset, expected in enumerate([ids[1],ids[2],ids[0]]):
                response = self.client.get('/api/v1/withdrawals', params={**params,'offset':offset})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['total'], 3)
                self.assertEqual(response.json()['items'][0]['id'], expected)
            for key, direction, expected in [('exchange_value','desc',ids[0]),('created_at','asc',ids[2]),('id','asc',ids[0]),('id','desc',ids[2])]:
                result = self.client.get('/api/v1/withdrawals',params={**params,'sort':key,'order':direction}).json()
                self.assertEqual(result['items'][0]['id'],expected)
            self.assertEqual(self.client.get('/api/v1/withdrawals',params={'sort':'invalid'}).status_code,422)
            self.assertEqual(self.client.get('/api/v1/withdrawals',params={'order':'invalid'}).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_(ids)))
                session.commit()

    def test_withdrawal_reasonless_refusal_and_atomic_batch(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            rows = [Withdrawal(status=0), Withdrawal(status=0), Withdrawal(status=0), Withdrawal(status=1)]
            session.add_all(rows)
            session.commit()
            ids = [row.id for row in rows]
        try:
            operator = self.login_headers('operator-test', 'Operator-Test-123!')
            self.assertEqual(self.client.post(f'/api/v1/withdrawals/{ids[0]}/refuse', headers=operator).status_code, 403)
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-refuse', json={'ids':ids[:2]}, headers=operator).status_code, 403)
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-refuse', json={'ids':[]}).status_code, 422)
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-refuse', json={'ids':[ids[1],ids[3]]}).status_code, 409)
            with SessionLocal() as session:
                self.assertEqual(session.get(Withdrawal, ids[1]).status, 0)
            response = self.client.post(f'/api/v1/withdrawals/{ids[0]}/refuse')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['target_status'], 4)
            self.assertEqual(response.json()['reason'], '')
            self.assertTrue(response.json()['audit_operator_id'])
            self.assertEqual(self.client.post(f'/api/v1/withdrawals/{ids[0]}/refuse').status_code, 409)
            response = self.client.post('/api/v1/withdrawals/batch-refuse', json={'ids':[ids[1],ids[2],ids[1]]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['updated'], 2)
            self.assertTrue(all(row['status']==2 and row['audit_operator_id'] for row in response.json()['items']))
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_(ids)))
                session.commit()

    def test_withdrawal_reference_display_fields_and_product_filter(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            rows = [
                Withdrawal(good_name='fixture 100% product', device_manufacturer='fixture phone', check_status_txt='review supplied', exchange_value=125, status=0, sub_msg='gateway message', reason='review reason'),
                Withdrawal(good_name='fixture 1000 product', exchange_value=200, status=1),
            ]
            session.add_all(rows)
            session.commit()
            ids = [row.id for row in rows]
        try:
            response = self.client.get('/api/v1/withdrawals', params={'good_name': '100%', 'status': 0})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload['total'], 1)
            row = payload['items'][0]
            self.assertEqual(row['id'], ids[0])
            self.assertEqual(row['good_name'], 'fixture 100% product')
            self.assertEqual(row['device_manufacturer'], 'fixture phone')
            self.assertEqual(row['check_status_txt'], 'review supplied')
            self.assertEqual(row['exchange_value'], 125)
            self.assertEqual(row['sub_msg'], 'gateway message')
            self.assertEqual(row['reason'], 'review reason')
            self.assertEqual(self.client.get('/api/v1/withdrawals', params={'good_name':'100%', 'status':1}).json()['total'], 0)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_(ids)))
                session.commit()

    def test_withdrawal_batch_rejection_validation_and_rollback(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            rows = [Withdrawal(status=0), Withdrawal(status=0), Withdrawal(status=1)]
            session.add_all(rows)
            session.commit()
            ids = [row.id for row in rows]
        for reason in ['', '   ']:
            result = self.client.post('/api/v1/withdrawals/batch-reject', json={'ids': ids[:2], 'reason': reason})
            self.assertEqual(result.status_code, 422)
        result = self.client.post('/api/v1/withdrawals/batch-reject', json={'ids': [ids[0], ids[2]], 'reason': 'review reason'})
        self.assertEqual(result.status_code, 409)
        with SessionLocal() as session:
            self.assertEqual(session.get(Withdrawal, ids[0]).status, 0)
            self.assertEqual(session.get(Withdrawal, ids[1]).status, 0)
        result = self.client.post('/api/v1/withdrawals/batch-reject', json={'ids': ids[:2], 'reason': ' review reason '})
        self.assertEqual(result.status_code, 200)
        for row in result.json()['items']:
            self.assertEqual(row['status'], 2)
            self.assertEqual(row['reason'], 'review reason')
            self.assertTrue(row['audit_operator_id'])

    def test_review_patch_transitions_and_status_alias(self) -> None:
        from app.main_from_txt import Withdrawal, Subsidy
        with SessionLocal() as session:
            withdrawal = Withdrawal(status=0, plan_status=0)
            rejected = Withdrawal(status=0, plan_status=0)
            subsidy = Subsidy(status=0)
            session.add_all([withdrawal, rejected, subsidy])
            session.commit()
            wid, rid, sid = withdrawal.id, rejected.id, subsidy.id
        path = f'/api/v1/withdrawals/{wid}'
        self.assertEqual(self.client.patch(path, json={'plan_status': 1}).status_code, 409)
        response = self.client.patch(path, json={'status': 1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['audit_operator_id'])
        response = self.client.patch(path, json={'plan_status': 1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['transfer_operator_id'])
        self.assertEqual(self.client.patch(path, json={'plan_status': 0}).status_code, 409)
        self.assertEqual(self.client.patch(path, json={'status': 0}).status_code, 409)
        for resource, item_id, field in [('withdrawals', rid, 'reason'), ('subsidies', sid, 'sub_msg')]:
            path = f'/api/v1/{resource}/{item_id}'
            self.assertEqual(self.client.patch(path, json={'status': 4, field: ' '}).status_code, 422)
            response = self.client.patch(path, json={'status': 4, field: ' alias rejection '})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 2)
            self.assertEqual(response.json()[field], 'alias rejection')
            listing = self.client.get(f'/api/v1/{resource}', params={'status': 4, 'limit': 200}).json()
            self.assertIn(item_id, [row['id'] for row in listing['items']])

    def test_subsidy_batch_atomicity_and_permissions(self) -> None:
        from app.main_from_txt import Subsidy
        with SessionLocal() as session:
            records=[Subsidy(status=0),Subsidy(status=0),Subsidy(status=1)]
            session.add_all(records);session.commit();ids=[r.id for r in records]
        try:
            operator=self.login_headers('operator-test','Operator-Test-123!')
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-approve',json={'ids':ids[:2]},headers=operator).status_code,403)
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-approve',json={'ids':[ids[0],ids[2]]}).status_code,409)
            with SessionLocal() as session:self.assertEqual(session.get(Subsidy,ids[0]).status,0)
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-reject',json={'ids':ids[:2],'message':' '}).status_code,422)
            result=self.client.post('/api/v1/subsidies/batch-reject',json={'ids':ids[:2],'message':'Batch test reason'})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()['updated'],2)
            for row in result.json()['items']:
                self.assertEqual(row['status'],2)
                self.assertEqual(row['sub_msg'],'Batch test reason')
                self.assertTrue(row['audit_operator_id'])
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-approve',json={'ids':ids[:2]}).status_code,409)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Subsidy).where(Subsidy.id.in_(ids)));session.commit()

    def test_coin_log_filters_and_summary(self) -> None:
        from app.main_from_txt import CoinLog
        with SessionLocal() as session:
            session.add_all([CoinLog(user_id=695016,agent_id=133,game_id=237,coin=5,remark='coin-filter-match'),CoinLog(user_id=695016,agent_id=133,game_id=237,coin=-2,remark='coin-filter-other')])
            session.commit()
        try:
            response=self.client.get('/api/v1/coin-logs',params={'q':'coin-filter-match','game_ad_status':0})
            self.assertEqual(response.status_code,200)
            data=response.json()
            self.assertEqual(data['total'],1)
            self.assertEqual(data['summary']['change'],5)
            row=data['items'][0]
            self.assertTrue(row['username'])
            self.assertTrue(row['game_name'])
            self.assertTrue(row['agent_name'])
            self.assertEqual(self.client.get('/api/v1/coin-logs',params={'q':'coin-filter','username':'no-such-user'}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/coin-logs',params={'remark':'coin-filter','created_to':'2000-01-01T00:00:00'}).json()['summary']['change'],0)
        finally:
            with SessionLocal() as session:
                session.execute(delete(CoinLog).where(CoinLog.remark.in_(['coin-filter-match','coin-filter-other'])));session.commit()

    def test_reference_ad_filter_contract(self) -> None:
        with SessionLocal() as session:
            records=[AdRecord(request_id='contract-check-a', coin=100, estimate_income=2, is_fu=1, fu_type=3, is_look=0),
                     AdRecord(request_id='contract-check-b', coin=2, estimate_income=100, is_fu=0, fu_type=1, is_look=1)]
            session.add_all(records);session.commit()
            ids=[item.id for item in records]
        try:
            params={'q':'contract-check','estimate_income_min':1,'estimate_income_max':3,'is_fu':1,'fu_type':3,'is_look':0}
            result=self.client.get('/api/v1/ads',params=params)
            self.assertEqual(result.status_code,200)
            self.assertEqual([row['id'] for row in result.json()['items']],[ids[0]])
            self.assertEqual(self.client.get('/api/v1/ads',params={**params,'fu_type':2}).json()['total'],0)
            exported=self.client.get('/api/v1/ads/export',params=params)
            self.assertEqual(exported.status_code,200)
            self.assertIn('contract-check-a',exported.text)
            self.assertNotIn('contract-check-b',exported.text)
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.id.in_(ids)));session.commit()

    def test_profile_save_and_private_operation_log(self) -> None:
        before = self.client.get('/api/auth/me').json()
        response = self.client.patch('/api/auth/me', json={'display_name':'Profile test', 'password':''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['display_name'], 'Profile test')
        self.assertNotIn('password_hash', response.json())
        try:
            self.assertEqual(self.client.patch('/api/auth/me', json={'display_name':'  '}).status_code, 422)
            self.assertEqual(self.client.patch('/api/auth/me', json={'display_name':'Valid','password':'short'}).status_code, 422)
            logs = self.client.get('/api/auth/operations', params={'q':'/api/auth/me'}).json()
            self.assertGreaterEqual(logs['total'], 1)
            operator = self.login_headers('operator-test', 'Operator-Test-123!')
            other_logs = self.client.get('/api/auth/operations', params={'q':'/api/auth/me'}, headers=operator).json()
            self.assertEqual(other_logs['total'], 0)
            self.assertEqual(self.client.get('/api/auth/operations', headers={'Authorization':'Bearer invalid'}).status_code, 401)
        finally:
            self.client.patch('/api/auth/me', json={'display_name':before['display_name']})

    def test_member_registration_filters(self) -> None:
        with SessionLocal() as session:
            items = [Member(username='registration-check-a', ip='192.0.2.1', last_login_ip='198.51.100.1', created_at=datetime(2026, 1, 10, 0, 0)),
                     Member(username='registration-check-b', ip='192.0.2.2', created_at=datetime(2026, 1, 10, 23, 59, 59)),
                     Member(username='registration-check-c', ip='192.0.2.1', created_at=datetime(2026, 1, 11, 0, 0))]
            session.add_all(items)
            session.commit()
            ids = [item.id for item in items]
        try:
            def query(**params):
                response = self.client.get('/api/v1/members', params={'username':'registration-check', **params})
                self.assertEqual(response.status_code, 200)
                return response.json()['total']
            self.assertEqual(query(create_time='2026-01-10'), 2)
            self.assertEqual(query(create_time='2026-01-10 - 2026-01-11', ip='192.0.2.1'), 2)
            self.assertEqual(query(create_time='2026-01-10', ip='192.0.2.1'), 1)
            self.assertEqual(query(ip='198.51.100.1'), 0)
            self.assertEqual(query(ip='%'), 0)
            for value in ['invalid', '2026-01-11 - 2026-01-10']:
                self.assertEqual(self.client.get('/api/v1/members', params={'create_time':value}).status_code, 422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)))
                session.commit()

    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        with SessionLocal() as session:
            for username, password, role, display_name in [
                ("operator-test", "Operator-Test-123!", "operator", "娴嬭瘯杩愯惀"),
                ("reviewer-test", "Reviewer-Test-123!", "reviewer", "娴嬭瘯瀹℃牳"),
                ("risk-test", "Risk-Test-123!", "risk", "娴嬭瘯椋庢帶"),
            ]:
                if session.scalar(select(AdminUser).where(AdminUser.username == username)) is None:
                    password_hash, password_salt = hash_password(password)
                    session.add(
                        AdminUser(
                            username=username,
                            password_hash=password_hash,
                            password_salt=password_salt,
                            display_name=display_name,
                            role=role,
                            status=1,
                        )
                    )
            session.commit()
        login_response = cls.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Test-Admin-123!"},
        )
        if login_response.status_code != 200:
            raise RuntimeError(f"娴嬭瘯绠＄悊鍛樼櫥褰曞け璐? {login_response.text}")
        cls.client.headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"

    def login_headers(self, username: str, password: str) -> dict[str, str]:
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        engine.dispose()
        TEST_DATABASE.unlink(missing_ok=True)

    def cleanup_ad_alert_test_data(self, batch_id: int | None = None) -> None:
        with SessionLocal() as session:
            session.execute(delete(AdRecord).where(AdRecord.request_id.in_(["alert-duplicate-request", "alert-group-mismatch"])))
            if batch_id is not None:
                session.execute(delete(AdImportError).where(AdImportError.batch_id == batch_id))
                batch = session.get(AdImportBatch, batch_id)
                if batch is not None:
                    session.delete(batch)
            session.commit()

    def test_agent_game_member_lifecycle(self) -> None:
        password = "Temporary-Password-123"
        agent_response = self.client.post(
            "/api/v1/agents",
            json={"name": "CRUD 娴嬭瘯涓讳綋", "user_name": "crud-test", "password": password},
        )
        self.assertEqual(agent_response.status_code, 201)
        agent = agent_response.json()
        self.assertNotIn("password", agent)

        with SessionLocal() as session:
            stored_agent = session.get(Agent, agent["id"])
            self.assertIsNotNone(stored_agent)
            self.assertNotEqual(stored_agent.password, password)
            self.assertTrue(stored_agent.salt)

        game_response = self.client.post(
            "/api/v1/games",
            json={
                "agent_id": agent["id"],
                "name": "CRUD 娴嬭瘯娓告垙",
                "game_key": "test.crud.game",
                "settings_json": '{"mode":"test"}',
            },
        )
        self.assertEqual(game_response.status_code, 201)
        game = game_response.json()

        member_response = self.client.post(
            "/api/v1/members",
            json={
                "agent_id": agent["id"],
                "game_id": game["id"],
                "username": "crud-member",
                "name": "娴嬭瘯浼氬憳",
            },
        )
        self.assertEqual(member_response.status_code, 201)
        member = member_response.json()

        update_response = self.client.patch(
            f"/api/v1/members/{member['id']}",
            json={"coin": 88.5, "vip": 2},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["coin"], 88.5)
        self.assertEqual(self.client.get(f"/api/v1/members/{member['id']}").status_code, 200)

        protected_delete = self.client.delete(f"/api/v1/agents/{agent['id']}")
        self.assertEqual(protected_delete.status_code, 409)

        invalid_scope = self.client.post(
            "/api/v1/members",
            json={"agent_id": agent["id"], "game_id": 237, "username": "invalid-scope"},
        )
        self.assertEqual(invalid_scope.status_code, 422)

        self.assertEqual(self.client.delete(f"/api/v1/members/{member['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/v1/games/{game['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/v1/agents/{agent['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/agents/{agent['id']}").status_code, 404)

    def test_authentication_is_required(self) -> None:
        unauthorized = self.client.get(
            "/api/v1/dashboard/summary",
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertEqual(unauthorized.status_code, 401)

        invalid_login = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        self.assertEqual(invalid_login.status_code, 401)

        current_admin = self.client.get("/api/auth/me")
        self.assertEqual(current_admin.status_code, 200)
        self.assertEqual(current_admin.json()["role"], "superadmin")

    def test_invalid_game_settings_json(self) -> None:
        response = self.client.post(
            "/api/v1/games",
            json={"agent_id": 133, "name": "鏃犳晥閰嶇疆", "settings_json": "[]"},
        )
        self.assertEqual(response.status_code, 422)

