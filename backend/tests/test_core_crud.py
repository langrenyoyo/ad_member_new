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

from app.main_from_txt import AdminUser, AdImportBatch, AdImportError, AdRecord, Agent, Member, SessionLocal, app, engine, hash_password, verify_password  # noqa: E402


class CoreCrudTestCase(unittest.TestCase):
    def test_agent_analysis_aggregation_ranges_scope_and_settings(self) -> None:
        from app.main_from_txt import Game, LotteryRecord, AgentAnalysisConfig
        with SessionLocal() as session:
            agents=[Agent(name='analysis A'),Agent(name='analysis B')];session.add_all(agents);session.flush();aid,bid=[row.id for row in agents]
            games=[Game(name='analysis game A',agent_id=aid),Game(name='analysis game B',agent_id=bid)];session.add_all(games);session.flush();gid,other=[row.id for row in games]
            members=[Member(username='analysis '+uuid4().hex,agent_id=aid,game_id=gid,coin_user=100,coin=12),Member(username='analysis '+uuid4().hex,agent_id=aid,game_id=gid,coin_user=50),Member(username='outside '+uuid4().hex,agent_id=bid,game_id=other)]
            session.add_all(members);session.flush();uids=[row.id for row in members]
            records=[LotteryRecord(user_id=uids[0],game_id=gid,lottery_price=price,status=state,network_status=network,created_at=when) for price,state,network,when in [(3,1,0,datetime(2040,1,1,16)),(1,0,1,datetime(2040,1,1,16)),(2,1,None,datetime(2040,1,1,15,59,59))]]
            records += [LotteryRecord(user_id=uids[1],game_id=gid,lottery_price=10,status=1,network_status=1,created_at=datetime(2040,1,1,16)),LotteryRecord(user_id=uids[2],game_id=other,lottery_price=999,status=1),LotteryRecord(user_id=uids[0],game_id=other,lottery_price=999,status=1)]
            session.add_all(records);session.commit()
        try:
            path=f'/api/v1/agents/{aid}/analysis';settings=f'/api/v1/agents/{aid}/analysis-settings'
            result=self.client.get(path,params={'limit':1}).json();self.assertEqual(result['total'],2);self.assertEqual(len(result['items']),1)
            self.assertEqual(result['echart_data']['echart_ip_data'],[{'name':'内网','value':1},{'name':'公网','value':2}])
            self.assertEqual(result['echart_data']['echart_scatter_data'],[[10.0,10.0],[6.0,2.0]])
            row=self.client.get(path,params={'sort':'coin_user','order':'desc'}).json()['items'][0]
            self.assertEqual(row['coin_user'],100);self.assertEqual(row['coin_user_total'],6);self.assertEqual(row['coin_every'],2);self.assertEqual(row['success_percent'],66.67)
            self.assertNotIn('password',row);self.assertNotIn('device_id',row)
            filtered=self.client.get(path,params={'created_from':'2040-01-02T00:00:00+08:00','created_to':'2040-01-02T00:00:00+08:00','success_percent_max':50}).json()
            self.assertEqual(filtered['total'],1);self.assertEqual(filtered['items'][0]['coin_user_total'],4)
            self.assertEqual(filtered['echart_data']['echart_scatter_data'],[[4.0,2.0]])
            self.assertEqual(self.client.get(path,params={'coin_user_total_min':7,'coin_every_max':10,'app_num_min':1}).json()['items'][0]['id'],uids[1])
            self.assertEqual(self.client.get(path,params={'coin_user_total_min':11}).json()['total'],0)
            for params in [{'coin_every_min':3,'coin_every_max':2},{'app_num_min':1.5},{'success_percent_max':101},{'sort':'username'},{'limit':201},{'coin_every_min':'nan'},{'created_from':'2040-02-02','created_to':'2040-01-01'}]:
                self.assertEqual(self.client.get(path,params=params).status_code,422,params)
            self.assertEqual(self.client.get(settings).json(),{'coin':[],'success':[],'apps':[]})
            with SessionLocal() as session:self.assertIsNone(session.get(AgentAnalysisConfig,aid))
            body={'coin':[dict(name='Small',minimum=0,maximum=6)],'success':[],'apps':[]}
            self.assertEqual(self.client.patch(settings,json=body).status_code,200)
            self.assertEqual(self.client.get(settings).json(),body)
            self.assertEqual(self.client.patch(settings,json={'apps':[dict(name='One',minimum=1,maximum=1)]}).json()['coin'],body['coin'])
            self.assertEqual(self.client.get(path).json()['echart_data']['echart_coin_data'],[{'name':'Small','value':1},{'name':'其它','value':1}])
            self.assertEqual(self.client.get(f'/api/v1/agents/{bid}/analysis-settings').json()['coin'],[])
            reviewer=self.login_headers('reviewer-test','Reviewer-Test-123!')
            self.assertFalse(self.client.get(path,headers=reviewer).json()['can_configure'])
            self.assertEqual(self.client.patch(settings,json=body,headers=reviewer).status_code,403)
            for bad in [{'coin':[dict(name='bad',minimum=5,maximum=2)]},{'coin':[dict(name='one',minimum=0,maximum=5),dict(name='two',minimum=5,maximum=10)]},{'coin':[dict(name=' ',minimum=0,maximum=5)]}]:
                self.assertEqual(self.client.patch(settings,json=bad).status_code,422)
            self.assertEqual(self.client.get('/api/v1/agents/999999999/analysis').status_code,404)
        finally:
            with SessionLocal() as session:
                session.execute(delete(AgentAnalysisConfig).where(AgentAnalysisConfig.agent_id==aid));session.execute(delete(LotteryRecord).where(LotteryRecord.user_id.in_(uids)));session.execute(delete(Member).where(Member.id.in_(uids)));session.execute(delete(Game).where(Game.id.in_([gid,other])));session.execute(delete(Agent).where(Agent.id.in_([aid,bid])));session.commit()

    def test_agent_batch_status_atomicity_and_capabilities(self) -> None:
        with SessionLocal() as session:
            rows = [Agent(name='batch agent '+str(i), status=1) for i in range(225)]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            path='/api/v1/agents/batch-status'
            operator=self.login_headers('operator-test','Operator-Test-123!')
            reviewer=self.login_headers('reviewer-test','Reviewer-Test-123!')
            self.assertTrue(all(self.client.get('/api/v1/agents',headers=operator).json()['permissions'].values()))
            permissions=self.client.get('/api/v1/agents',headers=reviewer).json()['permissions']
            self.assertEqual(permissions,dict(create=False,edit=False,delete=False,oss=False,batch_status=False,dashboard=True))
            self.assertEqual(self.client.post(path,headers=reviewer,json={'ids':ids,'status':0}).status_code,403)
            for body in [{'ids':[],'status':0},{'ids':ids,'status':2},{'ids':ids,'status':None},{'ids':ids+[999999999],'status':0}]:
                self.assertIn(self.client.post(path,json=body).status_code,[404,422])
            with SessionLocal() as session:
                self.assertTrue(all(row.status==1 for row in session.scalars(select(Agent).where(Agent.id.in_(ids)))))
            self.assertEqual(self.client.post(path,headers=operator,json={'ids':ids+[ids[0]],'status':0}).json(),{'updated':225})
            with SessionLocal() as session:
                self.assertTrue(all(row.status==0 for row in session.scalars(select(Agent).where(Agent.id.in_(ids)))))
            self.assertEqual(self.client.post(path,json={'ids':[ids[0]],'status':1}).json(),{'updated':1})
        finally:
            with SessionLocal() as session:session.execute(delete(Agent).where(Agent.id.in_(ids)));session.commit()

    def test_withdrawal_blacklist_lifecycle_permissions_and_source(self) -> None:
        from app.main_from_txt import Withdrawal, WithdrawalBlacklist, AdminOperation
        with SessionLocal() as session:
            member=Member(username='blacklist-'+uuid4().hex,status=1)
            session.add(member);session.flush()
            rows=[Withdrawal(user_id=member.id,receive_name='recipient '+uuid4().hex,receive_tel='0012345',status=value,exchange_value=125) for value in [0,1,2]]
            rows.append(Withdrawal(receive_name='',receive_tel='',status=0))
            session.add_all(rows);session.commit();ids=[row.id for row in rows];uid=member.id
        blacklist_ids=[]
        try:
            for wid in ids[:3]:
                path=f'/api/v1/withdrawals/{wid}'
                before=self.client.get(path).json()
                body={key:before[key] for key in ['receive_name','receive_tel']}
                result=self.client.post(path+'/blacklist',json=body)
                self.assertEqual(result.status_code,200,result.text)
                item=result.json();blacklist_ids.append(item['id'])
                self.assertEqual(item['receive_tel'],'0012345');self.assertEqual(item['status'],1)
                self.assertEqual(self.client.get(path).json(),before)
                self.assertEqual(self.client.post(path+'/blacklist',json=body).json()['id'],item['id'])
                self.assertEqual(self.client.patch('/api/v1/withdrawal-blacklist/'+str(item['id']),json={'status':0}).json()['status'],0)
                self.assertEqual(self.client.post(path+'/blacklist',json=body).json()['status'],1)
                self.assertEqual(self.client.post(path+'/blacklist',json={**body,'receive_tel':'changed'}).status_code,409)
                with SessionLocal() as session:
                    self.assertEqual(session.get(Member,uid).status,1)
                    self.assertEqual(session.scalar(select(WithdrawalBlacklist.source_withdrawal_id).where(WithdrawalBlacklist.id==item['id'])),wid)
            self.assertEqual(self.client.post(f'/api/v1/withdrawals/{ids[3]}/blacklist',json={'receive_name':'','receive_tel':''}).status_code,422)
            self.assertEqual(self.client.post('/api/v1/withdrawals/999999999/blacklist',json={'receive_name':'','receive_tel':''}).status_code,404)
            entry='/api/v1/withdrawal-blacklist/'+str(blacklist_ids[0])
            for value in [None,2,-1,'invalid']:
                self.assertEqual(self.client.patch(entry,json={'status':value}).status_code,422)
            operator=self.login_headers('operator-test','Operator-Test-123!')
            self.assertEqual(self.client.patch(entry,json={'status':0},headers=operator).status_code,403)
            self.assertEqual(self.client.post(f'/api/v1/withdrawals/{ids[0]}/blacklist',json={'receive_name':'','receive_tel':''},headers=operator).status_code,403)
            self.assertEqual(self.client.patch('/api/v1/withdrawal-blacklist/999999999',json={'status':0}).status_code,404)
            with SessionLocal() as session:
                operations=session.scalars(select(AdminOperation).where(AdminOperation.path==f'/api/v1/withdrawals/{ids[0]}/blacklist')).all()
                self.assertEqual(len(operations),2)
                self.assertTrue(all(row.admin_id>0 for row in operations))
        finally:
            with SessionLocal() as session:
                session.execute(delete(WithdrawalBlacklist).where(WithdrawalBlacklist.id.in_(blacklist_ids)))
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_(ids)))
                session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_withdrawal_blacklist_exact_filters_dates_and_pagination(self) -> None:
        from app.main_from_txt import WithdrawalBlacklist
        prefix=uuid4().hex
        with SessionLocal() as session:
            rows=[WithdrawalBlacklist(receive_name=prefix+name,receive_tel=tel,status=state,created_at=when,updated_at=when) for name,tel,state,when in [
                ('%_', '00123',1,datetime(2040,1,1,15,59,59)),
                ('%_', '00124',0,datetime(2040,1,1,16)),
                ('zz', '00123',1,datetime(2040,1,2,16))]]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            path='/api/v1/withdrawal-blacklist'
            result=self.client.get(path,params={'receive_name':prefix+'%_','sort':'created_at','order':'asc','limit':1}).json()
            self.assertEqual(result['total'],2);self.assertEqual(result['items'][0]['id'],ids[0])
            self.assertEqual(self.client.get(path,params={'receive_name':prefix+'%_','sort':'created_at','order':'asc','limit':1,'offset':1}).json()['items'][0]['id'],ids[1])
            params={'receive_name':prefix+'%_','receive_tel':'00123','status':1}
            self.assertEqual([r['id'] for r in self.client.get(path,params=params).json()['items']],[ids[0]])
            self.assertEqual(self.client.get(path,params={**params,'receive_tel':'123'}).json()['total'],0)
            self.assertEqual(self.client.get(path,params={**params,'receive_name':prefix}).json()['total'],0)
            params={'receive_name':prefix+'%_','created_from':'2040-01-02T00:00:00+08:00','created_to':'2040-01-02T00:00:00+08:00'}
            self.assertEqual([r['id'] for r in self.client.get(path,params=params).json()['items']],[ids[1]])
            self.assertEqual(self.client.get(path,params={**params,'created_to':'2040-01-01T23:59:59+08:00'}).status_code,422)
            for invalid in [{'status':2},{'limit':201},{'offset':-1},{'sort':'receive_name'},{'order':'invalid'}]:
                self.assertEqual(self.client.get(path,params=invalid).status_code,422)
        finally:
            with SessionLocal() as session:session.execute(delete(WithdrawalBlacklist).where(WithdrawalBlacklist.id.in_(ids)));session.commit()

    def test_game_statistics_continuous_series_and_region_fields(self) -> None:
        from datetime import UTC, timedelta
        from unittest.mock import patch
        from app.main_from_txt import Game, DailyActivity
        with SessionLocal() as session:
            games=[Game(name='continuous stats'),Game(name='outside stats')]
            session.add_all(games);session.flush();gid,other=[row.id for row in games]
            session.add_all([Member(username='region A',game_id=gid,address='广西壮族自治区南宁市',coin_user=25,created_at=datetime(2040,1,1,16)),
                Member(username='region B',game_id=gid,address='北京市海淀区',coin_user=75,created_at=datetime(2040,1,1,15,59,59)),
                Member(username='region unknown',game_id=gid,address='unknown',coin_user=900,created_at=datetime(2039,12,1)),
                Member(username='outside region',game_id=other,address='北京市',coin_user=900,created_at=datetime(2040,1,1,16))])
            session.add_all([AdRecord(game_id=gid,estimate_income=3,coin=5,created_at=datetime(2040,1,1,16),updated_at=datetime(2040,1,2,1)),
                AdRecord(game_id=gid,estimate_income=4,coin=6,created_at=datetime(2040,1,1,15,59,59),updated_at=datetime(2040,1,1)),
                AdRecord(game_id=other,estimate_income=900,created_at=datetime(2040,1,1,16),updated_at=datetime(2040,2,1)),
                DailyActivity(game_id=gid,date=date(2040,1,2),num=7)])
            session.commit()
        try:
            with patch('app.main_from_txt.now',return_value=datetime(2040,1,2,1,tzinfo=UTC)):
                data=self.client.get(f'/api/v1/games/{gid}/statistics').json()
            dates=[(date(2040,1,2)-timedelta(days=30-i)).isoformat() for i in range(31)]
            self.assertEqual(data['series_dates'],dates)
            self.assertEqual([row['date'] for row in data['metric_series']],dates)
            self.assertEqual([row['date'] for row in data['registration_series']],dates)
            self.assertEqual(data['metric_series'][-1],{'date':'2040-01-02','income':3,'coin':5,'activity':7,'clicks':None})
            self.assertEqual(data['metric_series'][-2]['income'],4)
            self.assertEqual(data['metric_series'][0],{'date':dates[0],'income':0,'coin':0,'activity':None,'clicks':None})
            self.assertEqual([row['count'] for row in data['registration_series']][-2:],[1,1])
            self.assertEqual(data['update_date'],'2040-01-02')
            self.assertEqual(data['mapdata'],[{'name':'北京','value':1,'coin':75,'rate':33.33},{'name':'广西','value':1,'coin':25,'rate':33.33}])
            self.assertEqual(data['mapdata1'],['北京','广西']);self.assertEqual(data['mapdata2'],[1,1])
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.game_id==gid));session.commit()
            self.assertIsNone(self.client.get(f'/api/v1/games/{gid}/statistics').json()['update_date'])
        finally:
            with SessionLocal() as session:
                for model in [AdRecord,Member,DailyActivity]:session.execute(delete(model).where(model.game_id.in_([gid,other])))
                session.execute(delete(Game).where(Game.id.in_([gid,other])));session.commit()

    def test_behavior_multiple_filters_intersect_scope_and_preserve_summaries(self) -> None:
        from app.main_from_txt import Game, LotteryRecord, MemberLoginLog, CoinLog, RiskRecord, Withdrawal
        models=[LotteryRecord,MemberLoginLog,CoinLog,RiskRecord,Withdrawal]
        with SessionLocal() as session:
            games=[Game(name='multi A%_'),Game(name='multi B'),Game(name='multi Azz')]
            session.add_all(games);session.flush();gids=[row.id for row in games]
            members=[Member(username='multi member',game_id=gids[0],name='recipient',address='fixture',coin=77),
                     Member(username='multi outside',game_id=gids[0])]
            session.add_all(members);session.flush();uid,other=[row.id for row in members]
            children=[Member(username='multi child A',parent_id=uid,game_id=gids[0]),
                      Member(username='multi child B',parent_id=uid,game_id=gids[1]),
                      Member(username='multi outside child',parent_id=other,game_id=gids[0])]
            session.add_all(children);session.flush();child_ids=[row.id for row in children]
            for model in models:
                for member_id,game_id in [(uid,gid) for gid in gids]+[(other,gids[0])]:
                    fields={'coin':5} if model is CoinLog else {'exchange_value':10 if member_id==uid else 900,'status':1} if model is Withdrawal else {}
                    session.add(model(user_id=member_id,game_id=game_id,**fields))
            session.commit()
        try:
            endpoints=['lottery-records','coin-logs','withdrawals','login-logs','member-daily-income']
            for endpoint in endpoints:
                path='/api/v1/'+endpoint
                params={'user_id':uid,'filter_user_id':uid,'game_name':'multi A%_'}
                response=self.client.get(path,params=params)
                self.assertEqual(response.status_code,200,endpoint)
                self.assertEqual(response.json()['total'],1,endpoint)
                self.assertEqual(response.json()['items'][0]['game_id'],gids[0],endpoint)
                self.assertEqual(self.client.get(path,params={**params,'filter_user_id':other}).json()['total'],0,endpoint)
                self.assertEqual(self.client.get(path,params={**params,'game_id':gids[1]}).json()['total'],0,endpoint)
                self.assertEqual(self.client.get(path,params={**params,'game_name':'%_'}).json()['total'],0 if endpoint=='login-logs' else 1,endpoint)
                self.assertEqual(self.client.get(path,params={**params,'game_name':'multi'}).json()['total'],0 if endpoint=='login-logs' else 3,endpoint)
                self.assertEqual(self.client.get(path,params={**params,'filter_user_id':'invalid'}).status_code,422,endpoint)
            risk='/api/v1/risk/history'
            self.assertEqual(self.client.get(risk,params={'member_id':uid,'game_name':'%_'}).json()['total'],1)
            self.assertEqual(self.client.get(risk,params={'member_id':uid,'user_id':other,'game_name':'%_'}).json()['total'],0)
            address='/api/v1/member-addresses'
            self.assertEqual(self.client.get(address,params={'user_id':uid,'filter_user_id':uid,'game_name':'multi A%_'}).json()['total'],1)
            self.assertEqual(self.client.get(address,params={'user_id':uid,'game_name':'multi'}).json()['total'],0)
            self.assertEqual(self.client.get(address,params={'user_id':uid,'filter_user_id':other}).json()['total'],0)
            children=self.client.get('/api/v1/members',params={'parent_id':uid,'game_name_contains':'%_'}).json()
            self.assertEqual([row['id'] for row in children['items']],[child_ids[0]])
            self.assertEqual(self.client.get('/api/v1/members',params={'parent_id':uid,'game_name':'multi'}).json()['total'],0)
            coins=self.client.get('/api/v1/coin-logs',params={'user_id':uid,'filter_user_id':other}).json()
            self.assertEqual(coins['summary']['change'],0);self.assertEqual(coins['member_summary']['coin'],77)
            withdrawals=self.client.get('/api/v1/withdrawals',params={'user_id':uid,'filter_user_id':other}).json()
            self.assertEqual(withdrawals['total'],0);self.assertEqual(withdrawals['summary']['withdrawn'],30)
        finally:
            with SessionLocal() as session:
                for model in models:session.execute(delete(model).where(model.user_id.in_([uid,other])))
                session.execute(delete(Member).where(Member.id.in_([uid,other,*child_ids])))
                session.execute(delete(Game).where(Game.id.in_(gids)));session.commit()

    def test_member_daily_income_separates_games_and_keeps_group_ids(self) -> None:
        from app.main_from_txt import Game, CoinLog
        with SessionLocal() as session:
            games=[Game(name='daily group A'),Game(name='daily group B')]
            session.add_all(games);session.flush();a,b=[row.id for row in games]
            members=[Member(username='daily group member',game_id=a),Member(username='daily group outside',game_id=a)]
            session.add_all(members);session.flush();uid,other=[row.id for row in members]
            session.add_all([CoinLog(user_id=uid,game_id=a,coin=2,created_at=datetime(2040,1,1,15,59,59)),
                CoinLog(user_id=uid,game_id=a,coin=3,created_at=datetime(2040,1,1,16)),
                CoinLog(user_id=uid,game_id=b,coin=7,created_at=datetime(2040,1,1,16)),
                CoinLog(user_id=uid,game_id=a,coin=-1,created_at=datetime(2040,1,2,15,59,59)),
                CoinLog(user_id=uid,game_id=b,coin=11,created_at=datetime(2040,1,2,16)),
                CoinLog(user_id=other,game_id=a,coin=900,created_at=datetime(2040,1,1,16))]);session.commit()
        try:
            path='/api/v1/member-daily-income';params={'user_id':uid,'sort':'coin','order':'asc'}
            all_rows=self.client.get(path,params=params).json()['items']
            indexed={(row['game_id'],row['date']):row for row in all_rows}
            self.assertEqual({key:row['coin'] for key,row in indexed.items()},
                             {(a,'2040-01-01'):2,(a,'2040-01-02'):2,(b,'2040-01-02'):7,(b,'2040-01-03'):11})
            self.assertEqual(len({row['id'] for row in all_rows}),4)
            self.assertTrue(all(row['game_name']==('daily group A' if row['game_id']==a else 'daily group B') for row in all_rows))
            for index,row in enumerate(all_rows):
                page=self.client.get(path,params={**params,'limit':1,'offset':index}).json()
                self.assertEqual(page['total'],4);self.assertEqual(page['items'],[row])
            filtered=self.client.get(path,params={**params,'game_id':b,'date_from':'2040-01-02','date_to':'2040-01-02'}).json()
            self.assertEqual(filtered['items'],[indexed[(b,'2040-01-02')]])
            self.assertEqual(self.client.get(path,params={**params,'game_name':'group B'}).json()['total'],2)
            self.assertEqual(self.client.get(path,params={**params,'date_from':'0001-01-01','date_to':'9999-12-31'}).json()['items'],all_rows)
        finally:
            with SessionLocal() as session:
                session.execute(delete(CoinLog).where(CoinLog.user_id.in_([uid,other])))
                session.execute(delete(Member).where(Member.id.in_([uid,other])))
                session.execute(delete(Game).where(Game.id.in_([a,b])));session.commit()

    def test_member_device_fallback_validation_and_delete_dependencies(self) -> None:
        from app.main_from_txt import MemberDevice, MemberAppUsage, AdminOperation, Game
        with SessionLocal() as session:
            members=[Member(username='device-fallback',device_id='registered',last_login_device_id='last-device'),
                     Member(username='empty-device'),Member(username='usage-only')]
            game=Game(name='usage-only game');session.add(game)
            session.add_all(members);session.commit();uid,empty,usage=[member.id for member in members];gid=game.id
        path=f'/api/v1/members/{uid}/device-ban'
        try:
            self.assertEqual(self.client.patch('/api/v1/members/999999999/device-ban',json={
                'target':'device','banned':True,'expected_identifier':'missing'}).status_code,404)
            self.assertEqual(self.client.patch(f'/api/v1/members/{empty}/device-ban',json={
                'target':'device','banned':True,'expected_identifier':'missing'}).status_code,422)
            self.assertEqual(self.client.patch(path,json={
                'target':'imei','banned':True,'expected_identifier':'missing'}).status_code,422)
            self.assertEqual(self.client.patch(path,json={
                'target':'device','banned':True,'expected_identifier':''}).status_code,422)
            self.assertEqual(self.client.patch(path,json={
                'target':'unknown','banned':True,'expected_identifier':'last-device'}).status_code,422)
            with SessionLocal() as session:
                self.assertIsNone(session.get(MemberDevice,uid));self.assertIsNone(session.get(MemberDevice,empty))
            summary=self.client.get('/api/v1/lottery-records',params={'user_id':uid}).json()['member_summary']
            self.assertEqual(summary['device']['device_id'],'last-device')
            self.assertIsNone(summary['total_clicks']);self.assertEqual(summary['device']['imei'],'')
            operator=self.login_headers('operator-test','Operator-Test-123!')
            response=self.client.patch(path,json={'target':'device','banned':True,'expected_identifier':'last-device'},headers=operator)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['device']['device_id_ban'],1)
            self.assertEqual(self.client.delete(f'/api/v1/members/{uid}',headers=operator).status_code,409)
            with SessionLocal() as session:
                session.add(MemberAppUsage(user_id=usage,game_id=gid,app_name='fixture'))
                session.commit()
            self.assertEqual(self.client.delete(f'/api/v1/members/{usage}',headers=operator).status_code,409)
            self.assertEqual(self.client.delete(f'/api/v1/games/{gid}',headers=operator).status_code,409)
            self.assertEqual(self.client.delete(f'/api/v1/members/{empty}',headers=operator).status_code,204)
        finally:
            with SessionLocal() as session:
                for model in [MemberDevice,MemberAppUsage]:session.execute(delete(model).where(model.user_id.in_([uid,empty,usage])))
                session.execute(delete(AdminOperation).where(AdminOperation.path==path))
                session.execute(delete(Member).where(Member.id.in_([uid,empty,usage])))
                session.execute(delete(Game).where(Game.id==gid))
                session.commit()

    def test_member_behavior_summary_device_bans_and_app_usage(self) -> None:
        from datetime import UTC
        from unittest.mock import patch
        from app.main_from_txt import Game, LotteryRecord, MemberDevice, MemberAppUsage, AdminOperation
        with SessionLocal() as session:
            games=[Game(name='device scope A'),Game(name='device scope B')]
            session.add_all(games);session.flush();gids=[game.id for game in games]
            members=[Member(username='device-user',game_id=gids[0],coin=17,device_id='device-A'),Member(username='device-other',game_id=gids[1])]
            session.add_all(members);session.flush();uid,other=[member.id for member in members]
            session.add(MemberDevice(user_id=uid,device_id='device-A',imei='imei-A',model='fixture model',
                risk_flag=0,usb_debugging=1,rooted=0,total_clicks=50,today_clicks=3,today_failed=1,counter_date=date(2040,1,2)))
            session.add_all([LotteryRecord(user_id=uid,game_id=gids[0],lottery_price=100,status=1,created_at=datetime(2040,1,1,15,59,59)),
                LotteryRecord(user_id=uid,game_id=gids[0],lottery_price=4,status=1,created_at=datetime(2040,1,1,16)),
                LotteryRecord(user_id=uid,game_id=gids[0],lottery_price=6,status=1,created_at=datetime(2040,1,2,15,59,59)),
                LotteryRecord(user_id=uid,game_id=gids[0],lottery_price=99,status=0,created_at=datetime(2040,1,2,1)),
                LotteryRecord(user_id=uid,game_id=gids[0],lottery_price=200,status=1,created_at=datetime(2040,1,2,16)),
                LotteryRecord(user_id=other,game_id=gids[0],lottery_price=300,status=1,created_at=datetime(2040,1,2,1)),
                LotteryRecord(user_id=uid,game_id=gids[1],lottery_price=8,status=1,created_at=datetime(2040,1,2,2))])
            session.add_all([MemberAppUsage(user_id=uid,game_id=gids[0],app_name='fixture A',package_name='test.a',count=2,duration_seconds=75,first_used_at=datetime(2040,1,2),last_used_at=datetime(2040,1,2,1)),
                MemberAppUsage(user_id=uid,game_id=gids[1],app_name='fixture B',package_name='test.b',last_used_at=datetime(2040,1,2,2)),
                MemberAppUsage(user_id=other,game_id=gids[0],app_name='outside')]);session.commit()
        path=f'/api/v1/members/{uid}/device-ban'
        try:
            with patch('app.main_from_txt.now',return_value=datetime(2040,1,2,1,tzinfo=UTC)):
                summary=self.client.get('/api/v1/lottery-records',params={'user_id':uid,'game_id':gids[0],'ip':'nonmatching'}).json()['member_summary']
                self.assertEqual((summary['coin'],summary['today_lottery_coin'],summary['today_average_coin']),(17,10,5))
                self.assertEqual((summary['total_clicks'],summary['today_clicks'],summary['today_failed']),(50,3,1))
                self.assertEqual(summary['device']['model'],'fixture model')
                multi=self.client.get('/api/v1/lottery-records',params={'user_id':uid}).json()['member_summary']
                self.assertEqual(multi['today_lottery_coin'],18)
                self.assertIsNone(self.client.get('/api/v1/lottery-records',params={'user_id':uid,'game_id':gids[1]}).json()['member_summary'])
            with patch('app.main_from_txt.now',return_value=datetime(2040,1,3,1,tzinfo=UTC)):
                summary=self.client.get('/api/v1/lottery-records',params={'user_id':uid}).json()['member_summary']
                self.assertIsNone(summary['today_clicks']);self.assertEqual(summary['total_clicks'],50)
            reviewer=self.login_headers('reviewer-test','Reviewer-Test-123!')
            body={'target':'device','banned':True,'expected_identifier':'device-A'}
            self.assertEqual(self.client.patch(path,json=body,headers=reviewer).status_code,403)
            self.assertEqual(self.client.patch(path,json={**body,'expected_identifier':'old-device'}).status_code,409)
            risk=self.login_headers('risk-test','Risk-Test-123!')
            result=self.client.patch(path,json=body,headers=risk)
            self.assertEqual(result.status_code,200);self.assertEqual(result.json()['device']['device_id_ban'],1)
            self.assertEqual(result.json()['device']['imei_id_ban'],0)
            self.client.patch(path,json=body,headers=risk)
            with SessionLocal() as session:
                self.assertEqual(len(session.scalars(select(AdminOperation).where(AdminOperation.path==path)).all()),1)
            result=self.client.patch(path,json={'target':'imei','banned':True,'expected_identifier':'imei-A'})
            self.assertEqual(result.json()['device']['imei_id_ban'],1)
            result=self.client.patch(path,json={**body,'banned':False})
            self.assertEqual(result.json()['device']['device_id_ban'],0)
            with SessionLocal() as session:
                self.assertEqual(session.get(Member,uid).status,1)
                self.assertEqual(session.get(MemberDevice,uid).imei_id_ban,1)
            app_path=f'/api/v1/members/{uid}/app-usage'
            data=self.client.get(app_path,params={'game_id':gids[0]}).json()
            self.assertEqual(data['total'],1);self.assertEqual(data['items'][0]['app_name'],'fixture A')
            self.assertEqual(data['items'][0]['duration_seconds'],75)
            data=self.client.get(app_path,params={'limit':1,'offset':1}).json()
            self.assertEqual(data['total'],2);self.assertEqual(data['items'][0]['app_name'],'fixture A')
            self.assertEqual(self.client.get(f'/api/v1/members/{other}/app-usage',params={'game_id':gids[1]}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/members/999999999/app-usage').status_code,404)
        finally:
            with SessionLocal() as session:
                for model in [LotteryRecord,MemberDevice,MemberAppUsage]:session.execute(delete(model).where(model.user_id.in_([uid,other])))
                session.execute(delete(AdminOperation).where(AdminOperation.path==path))
                session.execute(delete(Member).where(Member.id.in_([uid,other])))
                session.execute(delete(Game).where(Game.id.in_(gids)));session.commit()

    def test_member_filter_options_paging_scope_and_literal_search(self) -> None:
        from app.main_from_txt import Game
        prefix='lookup-'+uuid4().hex
        with SessionLocal() as session:
            agents=[Agent(name=prefix+' A',user_name=prefix+'a'),Agent(name=prefix+' B',user_name=prefix+'b')]
            session.add_all(agents);session.flush()
            games=[Game(name=prefix+' C',agent_id=agents[0].id),Game(name=prefix+' A',agent_id=agents[0].id),Game(name=prefix+' B%_',agent_id=agents[1].id)]
            session.add_all(games);session.commit()
            aids=[a.id for a in agents];gids=[g.id for g in games]
        try:
            path='/api/v1/member-filter-options/games'
            first=self.client.get(path,params={'q':prefix,'limit':1}).json()
            second=self.client.get(path,params={'q':prefix,'limit':1,'offset':1}).json()
            self.assertEqual(first['total'],3)
            self.assertEqual(first['items'],[{'id':gids[1],'name':prefix+' A'}])
            self.assertEqual(second['items'],[{'id':gids[2],'name':prefix+' B%_'}])
            scoped=self.client.get(path,params={'q':prefix,'agent_id':aids[0]}).json()
            self.assertEqual([r['id'] for r in scoped['items']],[gids[1],gids[0]])
            self.assertEqual(scoped['total'],2)
            self.assertEqual(self.client.get(path,params={'id':gids[2],'agent_id':aids[0]}).json()['items'],[])
            self.assertEqual(self.client.get(path,params={'q':prefix+' B%_'}).json()['items'],second['items'])
            self.assertEqual(self.client.get(path,params={'q':prefix,'offset':9}).json()['items'],[])
            agent=self.client.get('/api/v1/member-filter-options/agents',params={'agent_id':aids[0]}).json()
            self.assertEqual(agent['items'],[{'id':aids[0],'name':prefix+' A'}])
            for params in ({'limit':0},{'offset':-1},{'limit':101}):
                self.assertEqual(self.client.get(path,params=params).status_code,422)
            self.assertEqual(self.client.get('/api/v1/member-filter-options/unknown').status_code,422)
            self.assertEqual(self.client.get(path,headers={'Authorization':'Bearer invalid'}).status_code,401)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Game).where(Game.id.in_(gids)))
                session.execute(delete(Agent).where(Agent.id.in_(aids)));session.commit()

    def test_member_relation_fields_atomic_roundtrip(self) -> None:
        operator=self.login_headers('operator-test','Operator-Test-123!')
        created=self.client.post('/api/v1/members',json={'username':'relation-'+uuid4().hex,'parent_id':11,'ht_id':22,'ht_top_id':33},headers=operator)
        self.assertEqual(created.status_code,201,created.text)
        uid=created.json()['id'];path=f'/api/v1/members/{uid}'
        try:
            original=self.client.get(path).json()
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.patch(path,json={'parent_id':0,'ht_id':66,'ht_top_id':77},headers=risk).status_code,403)
            for invalid in (None,1.5,'not-an-id'):
                result=self.client.patch(path,json={'parent_id':0,'ht_id':66,'ht_top_id':invalid},headers=operator)
                self.assertEqual(result.status_code,422,result.text)
                self.assertEqual(self.client.get(path).json(),original)
            result=self.client.patch(path,json={'parent_id':0,'ht_id':66,'ht_top_id':77},headers=operator)
            self.assertEqual(result.status_code,200,result.text)
            with SessionLocal() as session:
                row=session.get(Member,uid)
                self.assertEqual((row.parent_id,row.ht_id,row.ht_top_id),(0,66,77))
            self.assertEqual(self.client.get(path).json()['ht_top_id'],77)
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_batch_status_scope_atomicity(self) -> None:
        with SessionLocal() as session:
            rows=[Member(username='batch-main-a',agent_id=991001,status=1),Member(username='batch-main-b',agent_id=991002,status=1)]
            session.add_all(rows);session.commit();ids=[r.id for r in rows]
        try:
            path='/api/v1/members/batch-status'
            for body,query,code in [({'ids':ids,'status':0},{'agent_id':991001},422),({'ids':[ids[0],999999999],'status':0},{},404),({'ids':ids,'status':2},{},422)]:
                self.assertEqual(self.client.post(path,json=body,params=query).status_code,code)
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.post(path,json={'ids':ids,'status':0},headers=risk).status_code,403)
            with SessionLocal() as session:self.assertEqual([session.get(Member,i).status for i in ids],[1,1])
            r=self.client.post(path,json={'ids':ids+[ids[0]],'status':0})
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['updated'],2)
            with SessionLocal() as session:self.assertEqual([session.get(Member,i).status for i in ids],[0,0])
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id.in_(ids)));session.commit()
    def test_member_create_scope_failure_is_atomic(self) -> None:
        from unittest.mock import patch
        from app.main_from_txt import Game
        token='create-scope-'+uuid4().hex
        with SessionLocal() as session:
            agents=[Agent(name=token+'a',user_name=token+'a'),Agent(name=token+'b',user_name=token+'b')]
            session.add_all(agents);session.flush()
            game=Game(name=token,agent_id=agents[0].id);session.add(game);session.commit()
            aid,bid=[a.id for a in agents];gid=game.id
        payload={'username':token,'password':'Fixture-123','pay_password':'Payment-123'}
        try:
            with patch('app.main_from_txt.hash_password') as hashing:
                for extra,code in [({'agent_id':999999999},404),({'game_id':999999999},404),({'agent_id':bid,'game_id':gid},422)]:
                    response=self.client.post('/api/v1/members',json={**payload,**extra})
                    self.assertEqual(response.status_code,code,response.text)
                hashing.assert_not_called()
            with SessionLocal() as session:
                self.assertIsNone(session.scalar(select(Member).where(Member.username==token)))
            response=self.client.post('/api/v1/members',json={**payload,'agent_id':aid,'game_id':gid})
            self.assertEqual(response.status_code,201,response.text)
            with SessionLocal() as session:
                member=session.scalar(select(Member).where(Member.username==token))
                self.assertEqual((member.agent_id,member.game_id),(aid,gid))
                self.assertTrue(verify_password('Fixture-123',member.password_hash,member.password_salt))
                self.assertTrue(verify_password('Payment-123',member.pay_password_hash,member.pay_password_salt))
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.username==token))
                session.execute(delete(Game).where(Game.id==gid))
                session.execute(delete(Agent).where(Agent.id.in_([aid,bid])));session.commit()

    def test_member_achievement_time_storage_contract(self) -> None:
        operator=self.login_headers('operator-test','Operator-Test-123!')
        created=self.client.post('/api/v1/members',json={'username':'date-contract','game_addiction_time':'2026-09-17 12:34:56'},headers=operator)
        self.assertEqual(created.status_code,201,created.text)
        uid=created.json()['id'];path=f'/api/v1/members/{uid}'
        try:
            original=self.client.get(path).json()
            for value in (None,'x'*65):
                result=self.client.patch(path,json={'game_addiction_time':value,'name':'must not save'},headers=operator)
                self.assertEqual(result.status_code,422,result.text)
                self.assertEqual(self.client.get(path).json(),original)
            # Strings are preserved without implicit UTC or browser-zone conversion.
            value='2026-10-01 08:09:10'
            self.assertEqual(self.client.patch(path,json={'game_addiction_time':value},headers=operator).status_code,200)
            with SessionLocal() as session:self.assertEqual(session.get(Member,uid).game_addiction_time,value)
            self.assertEqual(self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]['game_addiction_time'],value)
            self.assertEqual(self.client.patch(path,json={'game_addiction_time':''},headers=operator).status_code,200)
            self.assertEqual(self.client.get(path).json()['game_addiction_time'],'')
            self.assertEqual(self.client.post('/api/v1/members',json={'username':'bad-date-contract','game_addiction_time':'x'*65},headers=operator).status_code,422)
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_other_information_roundtrip(self) -> None:
        operator=self.login_headers('operator-test','Operator-Test-123!')
        created=self.client.post('/api/v1/members',json={'username':'other-info-fixture','otherlevel':'旧信息'},headers=operator)
        self.assertEqual(created.status_code,201,created.text)
        uid=created.json()['id'];path=f'/api/v1/members/{uid}'
        try:
            value='中文 <>& "quoted" '+('x'*300)
            response=self.client.patch(path,json={'otherlevel':value},headers=operator)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['otherlevel'],value)
            self.assertEqual(self.client.get(path).json()['otherlevel'],value)
            self.assertEqual(self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]['otherlevel'],value)
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.patch(path,json={'otherlevel':'not allowed'},headers=risk).status_code,403)
            self.assertEqual(self.client.patch(path,json={'otherlevel':None,'name':'must not save'},headers=operator).status_code,422)
            with SessionLocal() as session:
                self.assertEqual(session.get(Member,uid).otherlevel,value)
                self.assertNotEqual(session.get(Member,uid).name,'must not save')
            self.assertEqual(self.client.patch(path,json={'otherlevel':''},headers=operator).json()['otherlevel'],'')
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_image_upload_decode_persistence_and_permissions(self) -> None:
        from io import BytesIO
        from unittest.mock import patch
        from PIL import Image
        output=BytesIO();Image.new('RGB',(4,3),(25,80,120)).save(output,format='PNG');content=output.getvalue()
        operator=self.login_headers('operator-test','Operator-Test-123!')
        risk=self.login_headers('risk-test','Risk-Test-123!')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'MEMBER_IMAGE_DIR':directory}):
            response=self.client.post('/api/v1/member-images',content=content,headers={**operator,'Content-Type':'image/png'})
            self.assertEqual(response.status_code,201,response.text)
            url=response.json()['url'];self.assertLess(len(url),255)
            fetched=self.client.get(url)
            self.assertEqual(fetched.status_code,200)
            self.assertEqual(fetched.headers['content-type'],'image/png')
            with Image.open(BytesIO(fetched.content)) as decoded:
                self.assertEqual(decoded.size,(4,3));self.assertEqual(decoded.getpixel((0,0)),(25,80,120,255))
            created=self.client.post('/api/v1/members',json={'username':'image-fixture','image_url':url})
            self.assertEqual(created.status_code,201,created.text)
            uid=created.json()['id']
            try:
                self.assertEqual(self.client.get(f'/api/v1/members/{uid}').json()['image_url'],url)
                self.assertEqual(self.client.patch(f'/api/v1/members/{uid}',json={'image_url':None}).status_code,422)
                self.assertEqual(self.client.patch(f'/api/v1/members/{uid}',json={'image_url':'x'*256}).status_code,422)
            finally:
                with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()
            for invalid in (b'\x89PNG\r\n\x1a\n',b'<svg xmlns="http://www.w3.org/2000/svg"/>'):
                self.assertEqual(self.client.post('/api/v1/member-images',content=invalid,headers=operator).status_code,422)
            self.assertEqual(self.client.post('/api/v1/member-images',content=b'x'*(2*1024*1024+1),headers=operator).status_code,413)
            self.assertEqual(self.client.post('/api/v1/member-images',content=content,headers=risk).status_code,403)
            self.assertEqual(len(list(Path(directory).iterdir())),1)
            self.assertEqual(self.client.get('/api/member-images/not-an-image').status_code,404)

    def test_unconfigured_payment_all_entrypoints_preserve_records(self) -> None:
        from unittest.mock import patch
        from app.main_from_txt import Withdrawal
        from app.payment import configured_provider
        with SessionLocal() as session:
            rows=[Withdrawal(status=1,plan_status=0,reason='unchanged'),Withdrawal(status=0,plan_status=0)]
            session.add_all(rows);session.commit();wid,pending_id=[r.id for r in rows]
        try:
            path=f'/api/v1/withdrawals/{wid}'
            before=self.client.get(path).json()
            with patch.dict(os.environ,{'PAYMENT_PROVIDER':'alipay'}):
                self.assertFalse(configured_provider().available)
                self.assertEqual(configured_provider().name,'unconfigured')
                for _ in range(2):
                    for suffix in ['batch-transfer','batch-transfer-scheduled']:
                        result=self.client.post('/api/v1/withdrawals/'+suffix,json={'ids':[wid,wid]})
                        self.assertEqual(result.status_code,503,result.text)
                    self.assertEqual(self.client.post(path+'/transfer').status_code,503)
                    for plan_status in [1,2]:
                        self.assertEqual(self.client.patch(path,json={'plan_status':plan_status,'reason':'must roll back'}).status_code,503)
                        pending_path=f'/api/v1/withdrawals/{pending_id}'
                        pending_before=self.client.get(pending_path).json()
                        self.assertEqual(self.client.patch(pending_path,json={'status':1,'plan_status':plan_status,'sub_msg':'must roll back'}).status_code,409)
                        self.assertEqual(self.client.get(pending_path).json(),pending_before)
                    self.assertEqual(self.client.get(path).json(),before)
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-transfer',json={'ids':[wid,pending_id]}).status_code,409)
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-transfer',json={'ids':[]}).status_code,422)
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-transfer',json={'ids':[wid,999999999]}).status_code,404)
            operator=self.login_headers('operator-test','Operator-Test-123!')
            self.assertEqual(self.client.post(path+'/transfer',headers=operator).status_code,403)
            self.assertEqual(self.client.get(path).json(),before)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_([wid,pending_id])));session.commit()

    def test_member_payment_name_persists_independently(self) -> None:
        username='payment-name-'+uuid4().hex
        response=self.client.post('/api/v1/members',json={'username':username,'real_name':'实名认证甲','receive_name':'收款姓名乙'})
        self.assertEqual(response.status_code,201)
        uid=response.json()['id']
        try:
            data=self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]
            self.assertEqual(data['real_name'],'实名认证甲');self.assertEqual(data['receive_name'],'收款姓名乙')
            response=self.client.patch(f'/api/v1/members/{uid}',json={'receive_name':'中文 <>& 收款丙'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.client.get(f'/api/v1/members/{uid}').json()['receive_name'],'中文 <>& 收款丙')
            with SessionLocal() as session:
                member=session.get(Member,uid)
                self.assertEqual(member.receive_name,'中文 <>& 收款丙');self.assertEqual(member.real_name,'实名认证甲')
            self.assertEqual(self.client.patch(f'/api/v1/members/{uid}',json={'receive_name':None}).status_code,422)
            self.assertEqual(self.client.patch(f'/api/v1/members/{uid}',json={'receive_name':'字'*65}).status_code,422)
            self.assertEqual(self.client.patch(f'/api/v1/members/{uid}',json={'receive_name':''}).status_code,200)
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()
    def test_member_date_filter_uses_beijing_day(self) -> None:
        prefix='beijing-date-'+uuid4().hex
        moments=[datetime(2026,1,9,15,59,59),datetime(2026,1,9,16),datetime(2026,1,10,15,59,59,999999),datetime(2026,1,10,16)]
        with SessionLocal() as session:
            rows=[Member(username=prefix+str(i),created_at=moment) for i,moment in enumerate(moments)]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            response=self.client.get('/api/v1/members',params={'username':prefix,'create_time':'2026-01-10'})
            self.assertEqual(response.status_code,200)
            self.assertEqual({row['id'] for row in response.json()['items']},set(ids[1:3]))
            explicit=self.client.get('/api/v1/members',params={'username':prefix,'created_from':'2026-01-10T00:00:00+08:00','created_to':'2026-01-10T23:59:59.999999+08:00'})
            self.assertEqual({row['id'] for row in explicit.json()['items']},set(ids[1:3]))
            ranged=self.client.get('/api/v1/members',params={'username':prefix,'create_time':'2026-01-09 - 2026-01-10'})
            self.assertEqual({row['id'] for row in ranged.json()['items']},set(ids[:3]))
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)));session.commit()

    def test_agent_member_and_withdrawal_list_scope(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            members=[Member(username='scope-'+uuid4().hex,agent_id=998011),Member(username='scope-'+uuid4().hex,agent_id=998011),Member(username='scope-'+uuid4().hex,agent_id=998012)]
            session.add_all(members);session.flush()
            records=[Withdrawal(user_id=member.id,agent_id=member.agent_id,exchange_value=amount,status=status)
                     for member,amount,status in zip(members,[100,200,10000],[0,1,1])]
            session.add_all(records);session.commit()
            member_ids=[row.id for row in members];record_ids=[row.id for row in records]
        try:
            data=self.client.get('/api/v1/members',params={'agent_id':998011,'limit':1,'offset':0}).json()
            self.assertEqual(data['total'],2)
            first=data['items'][0]['id']
            data=self.client.get('/api/v1/members',params={'agent_id':998011,'limit':1,'offset':1}).json()
            self.assertEqual({first,data['items'][0]['id']},set(member_ids[:2]))
            data=self.client.get('/api/v1/withdrawals',params={'agent_id':998011}).json()
            self.assertEqual({row['id'] for row in data['items']},set(record_ids[:2]))
            self.assertEqual(data['summary']['pending'],100)
            self.assertEqual(data['summary']['withdrawn'],200)
            data=self.client.get('/api/v1/withdrawals',params={'agent_id':998011,'status':1}).json()
            self.assertEqual([row['id'] for row in data['items']],[record_ids[1]])
            data=self.client.get('/api/v1/withdrawals',params={'agent_id':998012}).json()
            self.assertEqual([row['id'] for row in data['items']],[record_ids[2]])
            self.assertEqual(data['summary']['withdrawn'],10000)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_(record_ids)))
                session.execute(delete(Member).where(Member.id.in_(member_ids)));session.commit()

    def test_behavior_history_single_and_multiple_game_scope(self) -> None:
        from app.main_from_txt import Game, LotteryRecord, MemberLoginLog
        with SessionLocal() as session:
            games=[Game(name='behavior scope A'),Game(name='behavior scope B')]
            session.add_all(games)
            member=Member(username='behavior scope member')
            other=Member(username='behavior scope other')
            session.add_all([member,other]);session.flush()
            gids=[game.id for game in games];uid=member.id;other_id=other.id
            for model in [LotteryRecord,MemberLoginLog]:
                session.add_all([model(user_id=uid,game_id=gids[0]),model(user_id=uid,game_id=gids[1]),model(user_id=other_id,game_id=gids[0])])
            session.commit()
        try:
            for endpoint in ['lottery-records','login-logs']:
                multi=self.client.get('/api/v1/'+endpoint,params={'user_id':uid})
                self.assertEqual(multi.status_code,200)
                self.assertEqual(multi.json()['total'],2)
                self.assertEqual({row['game_name'] for row in multi.json()['items']},{'behavior scope A','behavior scope B'})
                single=self.client.get('/api/v1/'+endpoint,params={'user_id':uid,'game_id':gids[0]}).json()
                self.assertEqual(single['total'],1)
                scoped=self.client.get(f'/api/v1/games/{gids[0]}/{endpoint}',params={'user_id':uid}).json()
                self.assertEqual(single['items'],scoped['items'])
        finally:
            with SessionLocal() as session:
                for model in [LotteryRecord,MemberLoginLog]:session.execute(delete(model).where(model.user_id.in_([uid,other_id])))
                session.execute(delete(Member).where(Member.id.in_([uid,other_id])))
                session.execute(delete(Game).where(Game.id.in_(gids)));session.commit()

    def test_dashboard_beijing_midnight_and_login_counts(self) -> None:
        from datetime import UTC
        from unittest.mock import patch
        rows = [
            Member(username='dashboard-before', created_at=datetime(2040, 1, 1, 15, 59, 59), last_login_time='2040-01-01T15:59:59Z'),
            Member(username='dashboard-start', created_at=datetime(2040, 1, 1, 16), last_login_time='2040-01-02T00:00:00+08:00'),
            Member(username='dashboard-end', created_at=datetime(2040, 1, 2, 15, 59, 59), last_login_time='2040-01-02T15:59:59Z'),
            Member(username='dashboard-future', created_at=datetime(2040, 1, 2, 16), last_login_time='2040-01-03T00:00:00+08:00'),
            Member(username='dashboard-invalid', created_at=datetime(2040, 1, 1), last_login_time='invalid'),
        ]
        with SessionLocal() as session:
            session.add_all(rows)
            session.commit()
            ids = [row.id for row in rows]
        try:
            with patch('app.main_from_txt.now', return_value=datetime(2040, 1, 1, 17, tzinfo=UTC)):
                summary = self.client.get('/api/v1/dashboard/summary').json()
                self.assertEqual(summary['today_new'], 2)
                self.assertEqual(summary['today_login'], 2)
                response = self.client.get('/api/v1/dashboard/registrations?days=3')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['items'], [
                    {'date': '2039-12-31', 'count': 0},
                    {'date': '2040-01-01', 'count': 2},
                    {'date': '2040-01-02', 'count': 2},
                ])
                self.assertEqual(self.client.get('/api/v1/dashboard/registrations?days=0').status_code, 422)
                self.assertEqual(len(self.client.get('/api/v1/dashboard/registrations?days=31').json()['items']), 31)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)))
                session.commit()

    def test_member_daily_income_uses_beijing_grouping(self) -> None:
        from app.main_from_txt import Game, CoinLog
        with SessionLocal() as session:
            game=Game(name='daily income behavior');session.add(game);session.flush()
            member=Member(username='daily income user',game_id=game.id);session.add(member);session.flush()
            session.add_all([CoinLog(user_id=member.id,game_id=game.id,coin=2,created_at=datetime(2026,1,1,7,59)),
                             CoinLog(user_id=member.id,game_id=game.id,coin=3,created_at=datetime(2026,1,1,8)),
                             CoinLog(user_id=member.id,game_id=game.id,coin=4,created_at=datetime(2026,1,2,8))]);session.commit();gid,uid=game.id,member.id
        try:
            data=self.client.get('/api/v1/member-daily-income',params={'user_id':uid,'game_id':gid}).json()
            self.assertEqual(data['total'],2);self.assertEqual(data['items'][0]['date'],'2026-01-01');self.assertEqual(data['items'][0]['coin'],5)
            self.assertEqual(data['items'][1]['coin'],4)
            self.assertEqual(data['items'][0]['username'],'daily income user')
            sorted_rows=self.client.get('/api/v1/member-daily-income',params={'user_id':uid,'sort':'coin','order':'desc','limit':1,'offset':1}).json()
            self.assertEqual(sorted_rows['total'],2)
            self.assertEqual(sorted_rows['items'][0]['coin'],4)
            filtered=self.client.get('/api/v1/member-daily-income',params={'user_id':uid,'date_from':'2026-01-02','date_to':'2026-01-02'}).json()
            self.assertEqual(filtered['total'],1)
            self.assertEqual(self.client.get('/api/v1/member-daily-income',params={'user_id':uid,'date_from':'2026-01-03','date_to':'2026-01-02'}).status_code,422)
            self.assertEqual(self.client.get('/api/v1/member-daily-income',params={'user_id':uid,'game_id':999999}).json()['total'],0)
        finally:
            with SessionLocal() as session:
                session.execute(delete(CoinLog).where(CoinLog.user_id==uid));session.execute(delete(Member).where(Member.id==uid));session.execute(delete(Game).where(Game.id==gid));session.commit()
    def test_member_address_endpoint_is_scoped_and_empty_safe(self) -> None:
        from app.main_from_txt import Game
        with SessionLocal() as session:
            game=Game(name='address behavior');session.add(game);session.flush()
            rows=[Member(username='address user',game_id=game.id,name='收件人',address='北京市海淀区测试路'),Member(username='empty address',game_id=game.id,address=''),Member(username='other address',game_id=0,address='outside')]
            session.add_all(rows);session.commit();ids=[row.id for row in rows];gid=game.id
        try:
            data=self.client.get('/api/v1/member-addresses',params={'user_id':ids[0],'game_id':gid}).json()
            self.assertEqual(data['total'],1);self.assertEqual(data['items'][0]['receive_address'],'北京市海淀区测试路')
            path='/api/v1/member-addresses'
            self.assertEqual(self.client.get(path,params={'user_id':ids[0],'receive_name':'收件人','receive_address':'北京市海淀区测试路'}).json()['total'],1)
            for key,value in [('receive_name','其他'),('receive_address','北京市'),('receive_tel','123'),('receive_postcode','100000')]:
                self.assertEqual(self.client.get(path,params={'user_id':ids[0],key:value}).json()['total'],0)
            self.assertEqual(self.client.get(path,params={'user_id':ids[0],'created_from':'2099-01-01T00:00:00Z'}).json()['total'],0)
            self.assertEqual(self.client.get(path,params={'user_id':ids[0],'created_from':'2026-02-01','created_to':'2026-01-01'}).status_code,422)
            self.assertEqual(self.client.get('/api/v1/member-addresses',params={'user_id':ids[0],'game_id':999999}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/member-addresses',params={'user_id':ids[1],'game_id':gid}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/member-addresses',params={'user_id':999999999}).status_code,404)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)));session.execute(delete(Game).where(Game.id==gid));session.commit()
    def test_coin_logs_member_scope_sort_and_type(self) -> None:
        from app.main_from_txt import CoinLog, Game
        with SessionLocal() as session:
            game=Game(name='coin behavior');session.add(game);session.flush()
            member=Member(username='coin behavior user',game_id=game.id,coin=7,freeze_coin=3,coin_user=12);session.add(member);session.flush()
            rows=[CoinLog(user_id=member.id,game_id=game.id,coin_before=10,coin=2,coin_after=12,type=10,remark='reward'),CoinLog(user_id=member.id,game_id=game.id,coin_before=12,coin=-5,coin_after=7,type=30,remark='exchange')]
            session.add_all(rows);session.commit();gid,uid=game.id,member.id
        try:
            path='/api/v1/coin-logs'; base={'game_id':gid,'user_id':uid}
            data=self.client.get(path,params={**base,'sort':'coin','order':'asc'}).json()
            self.assertEqual(data['total'],2);self.assertEqual(data['items'][0]['coin'],-5);self.assertEqual(data['summary']['change'],-3)
            self.assertEqual(data['member_summary'],{'coin':7,'freeze_coin':3,'coin_user':12})
            self.assertNotIn('member_summary',self.client.get(path,params={'user_id':uid,'game_id':999999999}).json())
            self.assertEqual(self.client.get(path,params={**base,'type':10}).json()['total'],1)
            self.assertEqual(self.client.get(path,params={**base,'sort':'remark'}).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(CoinLog).where(CoinLog.user_id==uid));session.execute(delete(Member).where(Member.id==uid));session.execute(delete(Game).where(Game.id==gid));session.commit()

    def test_device_risk_never_exposes_risk_events_as_members(self) -> None:
        from app.main_from_txt import RiskRecord
        token='device-scope-'+uuid4().hex
        with SessionLocal() as session:
            event=RiskRecord(user_id=123,game_id=901,tags=token)
            session.add(event);session.commit();event_id=event.id
        try:
            response=self.client.get('/api/v1/risk/devices')
            self.assertEqual(response.status_code,503)
            self.assertNotIn('items',response.json())
            history=self.client.get('/api/v1/risk/history',params={'tags':token}).json()
            self.assertEqual([row['id'] for row in history['items']],[event_id])
        finally:
            with SessionLocal() as session:session.execute(delete(RiskRecord).where(RiskRecord.id==event_id));session.commit()

    def test_behavior_risk_exact_member_scope(self) -> None:
        from app.main_from_txt import RiskRecord
        token='behavior-risk-'+uuid4().hex
        with SessionLocal() as session:
            rows=[RiskRecord(user_id=123,game_id=901,tags=token),RiskRecord(user_id=9123,game_id=901,tags=token),RiskRecord(user_id=123,game_id=902,tags=token)]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            path='/api/v1/risk/history'
            exact=self.client.get(path,params={'member_id':123,'game_id':901,'tags':token}).json()
            self.assertEqual([row['id'] for row in exact['items']],[ids[0]])
            multiple=self.client.get(path,params={'member_id':123,'tags':token}).json()
            self.assertEqual({row['id'] for row in multiple['items']},{ids[0],ids[2]})
            self.assertEqual(self.client.get(path,params={'user_id':'123','tags':token}).json()['total'],3)
            self.assertEqual(self.client.get(path,params={'member_id':123,'user_id':'9123','tags':token}).json()['total'],0)
        finally:
            with SessionLocal() as session:
                session.execute(delete(RiskRecord).where(RiskRecord.id.in_(ids)));session.commit()
    def test_game_member_batch_status_atomic_scope_and_permissions(self) -> None:
        from app.main_from_txt import Game
        with SessionLocal() as session:
            game=Game(name='batch members');session.add(game);session.flush();gid=game.id
            rows=[Member(username='batch-a',game_id=gid,status=1),Member(username='batch-b',game_id=gid,status=1),Member(username='batch-other',game_id=0,status=1)]
            session.add_all(rows);session.commit();ids=[row.id for row in rows]
        try:
            path=f'/api/v1/games/{gid}/members/batch-status'
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.post(path,json={'ids':ids[:2],'status':0},headers=risk).status_code,403)
            for payload,code in [({'ids':[],'status':0},422),({'ids':ids[:2],'status':2},422),({'ids':ids,'status':0},422),({'ids':[ids[0],999999999],'status':0},404)]:
                self.assertEqual(self.client.post(path,json=payload).status_code,code)
            with SessionLocal() as session:self.assertEqual([session.get(Member,i).status for i in ids],[1,1,1])
            operator=self.login_headers('operator-test','Operator-Test-123!')
            result=self.client.post(path,json={'ids':[ids[0],ids[1],ids[0]],'status':0},headers=operator)
            self.assertEqual(result.status_code,200);self.assertEqual(result.json()['updated'],2)
            with SessionLocal() as session:self.assertEqual([session.get(Member,i).status for i in ids],[0,0,1])
            self.assertEqual(self.client.post(path,json={'ids':ids[:2],'status':1},headers=operator).status_code,200)
            with SessionLocal() as session:self.assertEqual([session.get(Member,i).status for i in ids],[1,1,1])
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)));session.execute(delete(Game).where(Game.id==gid));session.commit()

    def test_member_coin_form_atomic_validation(self) -> None:
        with SessionLocal() as session:
            member=Member(username='coin-form',coin=12.5,freeze_coin=3)
            session.add(member);session.commit();uid=member.id
        try:
            path=f'/api/v1/members/{uid}'
            operator=self.login_headers('operator-test','Operator-Test-123!')
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.patch(path,json={'coin':25.75,'freeze_coin':4.5},headers=risk).status_code,403)
            for value in ['NaN','Infinity','-Infinity','1e999','invalid',None]:
                response=self.client.patch(path,json={'coin':25.75,'freeze_coin':value},headers=operator)
                self.assertEqual(response.status_code,422)
            with SessionLocal() as session:
                member=session.get(Member,uid);self.assertEqual((member.coin,member.freeze_coin),(12.5,3))
            result=self.client.patch(path,json={'coin':25.75,'freeze_coin':4.5},headers=operator)
            self.assertEqual(result.status_code,200)
            with SessionLocal() as session:
                member=session.get(Member,uid);self.assertEqual((member.coin,member.freeze_coin),(25.75,4.5))
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_sex_profile_roundtrip(self) -> None:
        with SessionLocal() as session:
            member=Member(username='profile-roundtrip',sex=2,card_no='00123',address='original')
            session.add(member);session.commit();uid=member.id
        try:
            path=f'/api/v1/members/{uid}'
            self.assertEqual(self.client.get(path).json()['sex'],2)
            self.assertEqual(self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]['sex'],2)
            result=self.client.patch(path,json={'sex':1,'address':'updated'})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()['sex'],1)
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertEqual((saved.sex,saved.address,saved.card_no),(1,'updated','00123'))
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_realname_state_roundtrip(self) -> None:
        with SessionLocal() as session:
            member=Member(username='realname-state',real_name='Stored Name',card_no='00123',receive_name='Payee')
            session.add(member);session.commit();uid=member.id
        try:
            path=f'/api/v1/members/{uid}'
            self.assertIsNone(self.client.get(path).json()['realname_enable'])
            operator=self.login_headers('operator-test','Operator-Test-123!')
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.patch(path,json={'realname_enable':1},headers=risk).status_code,403)
            for value in (1,0):
                result=self.client.patch(path,json={'realname_enable':value},headers=operator)
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['realname_enable'],value)
                self.assertEqual(self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]['realname_enable'],value)
                with SessionLocal() as session:
                    saved=session.get(Member,uid)
                    self.assertEqual((saved.realname_enable,saved.real_name,saved.card_no,saved.receive_name),(value,'Stored Name','00123','Payee'))
            for value in (2,-1,'unknown'):
                self.assertEqual(self.client.patch(path,json={'realname_enable':value,'real_name':'Invalid overwrite'},headers=operator).status_code,422)
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertEqual((saved.realname_enable,saved.real_name),(0,'Stored Name'))
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_internal_flag_editor_contract(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            member=Member(username='internal-editor',is_true=None,status=1,is_white=0,exchange_enable=1)
            session.add(member);session.flush();uid=member.id
            withdrawal=Withdrawal(user_id=uid,game_id=998899,exchange_value=12,status=0)
            session.add(withdrawal);session.commit();wid=withdrawal.id
        try:
            path=f'/api/v1/members/{uid}'
            self.assertIsNone(self.client.get(path).json()['is_true'])
            operator=self.login_headers('operator-test','Operator-Test-123!')
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.patch(path,json={'is_true':1},headers=risk).status_code,403)
            # JSON numbers are the browser contract for radio inputs, not strings.
            payload={'is_true':1,'exchange_enable':0,'status':0,'is_white':1}
            response=self.client.patch(path,json=payload,headers=operator)
            self.assertEqual(response.status_code,200,response.text)
            for key,value in payload.items():self.assertEqual(response.json()[key],value)
            self.assertEqual(self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]['is_true'],1)
            params={'game_id':998899,'is_true':1}
            self.assertEqual(self.client.get('/api/v1/withdrawals',params=params).json()['total'],1)
            for invalid in (2,-1,'invalid'):
                result=self.client.patch(path,json={'is_true':invalid,'status':1},headers=operator)
                self.assertEqual(result.status_code,422)
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertEqual((saved.is_true,saved.status,saved.exchange_enable,saved.is_white),(1,0,0,1))
            self.assertEqual(self.client.patch(path,json={'is_true':0},headers=operator).status_code,200)
            self.assertEqual(self.client.get('/api/v1/withdrawals',params=params).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/withdrawals',params={**params,'is_true':0}).json()['total'],1)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id==wid))
                session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_lottery_download_settings_roundtrip(self) -> None:
        with SessionLocal() as session:
            member=Member(username='lottery-settings')
            session.add(member);session.commit();uid=member.id
        try:
            path=f'/api/v1/members/{uid}'; operator=self.login_headers('operator-test','Operator-Test-123!')
            payload={'raffle_open':1,'raffle_num':12,'star_countdown':3.5,'over_countdown':9,'raffle_num2':7,'star_countdown2':1.25,'over_countdown2':8.75,'down_load':'https://example.test/app.apk'}
            result=self.client.patch(path,json=payload,headers=operator);self.assertEqual(result.status_code,200,result.text)
            for key,value in payload.items():self.assertEqual(result.json()[key],value)
            data=self.client.get(path).json()
            for key,value in payload.items():self.assertEqual(data[key],value)
            rejected=self.client.patch(path,json={'down_load':None,'raffle_num2':99},headers=operator)
            self.assertEqual(rejected.status_code,422)
            after=self.client.get(path).json()
            self.assertEqual(after['down_load'],payload['down_load'])
            self.assertEqual(after['raffle_num2'],7)
            for key,value in {'raffle_open':2,'raffle_num':-1,'star_countdown':-1,'raffle_num2':-2}.items():
                self.assertEqual(self.client.patch(path,json={key:value},headers=operator).status_code,422)
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertEqual((saved.raffle_num,saved.raffle_num2,saved.down_load),(12,7,'https://example.test/app.apk'))
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_passwords_are_hashed_and_not_serialized(self) -> None:
        from unittest.mock import patch
        with SessionLocal() as session:
            member=Member(username='password-contract');session.add(member);session.commit();uid=member.id
        try:
            path=f'/api/v1/members/{uid}'
            operator=self.login_headers('operator-test','Operator-Test-123!')
            result=self.client.patch(path,json={'password':'MemberPass-123','pay_password':'PayPass-456'},headers=operator)
            self.assertEqual(result.status_code,200,result.text)
            self.assertNotIn('password',result.json());self.assertNotIn('pay_password',result.json())
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertTrue(verify_password('MemberPass-123',saved.password_hash,saved.password_salt))
                self.assertTrue(verify_password('PayPass-456',saved.pay_password_hash,saved.pay_password_salt))
                self.assertNotEqual(saved.password_hash,'MemberPass-123')
                before=(saved.password_hash,saved.password_salt,saved.pay_password_hash,saved.pay_password_salt)
            secret_keys={'password','pay_password','password_hash','password_salt','pay_password_hash','pay_password_salt'}
            for data in (result.json(),self.client.get(path).json(),self.client.get('/api/v1/members',params={'id':uid}).json()['items'][0]):
                self.assertFalse(secret_keys.intersection(data),data.keys())
            risk=self.login_headers('risk-test','Risk-Test-123!')
            with patch('app.main_from_txt.hash_password') as hashing:
                self.assertEqual(self.client.patch(path,json={'password':'Forbidden-123'},headers=risk).status_code,403)
                self.assertEqual(self.client.patch(path,json={'password':'Rejected-123','down_load':None},headers=operator).status_code,422)
                hashing.assert_not_called()
            self.assertEqual(self.client.patch(path,json={'password':'Changed-123','pay_password':'x'},headers=operator).status_code,422)
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertEqual((saved.password_hash,saved.password_salt,saved.pay_password_hash,saved.pay_password_salt),before)
            # Independent password changes must not reset the payment password.
            self.assertEqual(self.client.patch(path,json={'password':'Changed-123'},headers=operator).status_code,200)
            with SessionLocal() as session:
                saved=session.get(Member,uid)
                self.assertTrue(verify_password('Changed-123',saved.password_hash,saved.password_salt))
                self.assertNotEqual(saved.password_salt,before[1])
                self.assertEqual((saved.pay_password_hash,saved.pay_password_salt),before[2:])
            for field,value in [('password','short'),('pay_password','123')]:
                self.assertEqual(self.client.patch(path,json={field:value},headers=operator).status_code,422)
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_member_switch_permissions_and_parent_account(self) -> None:
        from app.main_from_txt import Game
        with SessionLocal() as session:
            game=Game(name='switch regression')
            session.add(game);session.flush();gid=game.id
            parent=Member(username='switch-parent',name='Parent')
            session.add(parent);session.flush()
            child=Member(username='switch-child',parent_id=parent.id,game_id=gid,status=1,is_white=0,exchange_enable=1)
            session.add(child);session.commit();pid,uid=parent.id,child.id
        try:
            path=f'/api/v1/members/{uid}'
            data=self.client.get('/api/v1/members',params={'game_id':gid}).json()
            self.assertEqual(data['items'][0]['parent_username'],'switch-parent')
            self.assertEqual(data['items'][0]['parent_name'],'Parent')
            risk=self.login_headers('risk-test','Risk-Test-123!')
            self.assertEqual(self.client.patch(path,json={'is_white':1},headers=risk).status_code,200)
            for changes in [{'status':0},{'exchange_enable':0},{'is_white':0,'status':0}]:
                self.assertEqual(self.client.patch(path,json=changes,headers=risk).status_code,403)
            operator=self.login_headers('operator-test','Operator-Test-123!')
            for changes in [{'status':0},{'exchange_enable':0},{'is_white':0}]:
                self.assertEqual(self.client.patch(path,json=changes,headers=operator).status_code,200)
            for changes in [{'username':''},{'username':'   '},{'status':2},{'exchange_enable':2},{'is_white':2}]:
                self.assertEqual(self.client.patch(path,json=changes,headers=operator).status_code,422)
            with SessionLocal() as session:
                member=session.get(Member,uid)
                self.assertEqual((member.status,member.is_white,member.exchange_enable),(0,0,0))
                self.assertEqual(member.username,'switch-child')
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_([pid,uid])))
                session.execute(delete(Game).where(Game.id==gid));session.commit()

    def test_game_withdrawal_summary_filters_and_audit(self) -> None:
        from app.main_from_txt import Withdrawal
        with SessionLocal() as session:
            members = [Member(username='withdraw-internal',is_true=1), Member(username='withdraw-external',is_true=0)]
            session.add_all(members);session.flush()
            rows = [Withdrawal(game_id=998801,agent_id=998803,user_id=members[0].id,exchange_value=125,status=0),
                    Withdrawal(game_id=998801,agent_id=998803,user_id=members[1].id,exchange_value=40,status=1),
                    Withdrawal(game_id=998801,agent_id=998804,user_id=members[1].id,exchange_value=10,status=0),
                    Withdrawal(game_id=998802,agent_id=998803,user_id=members[0].id,exchange_value=999,status=1)]
            session.add_all(rows);session.commit()
            ids=[row.id for row in rows];member_ids=[member.id for member in members]
        try:
            base={'game_id':998801,'limit':1}
            data=self.client.get('/api/v1/withdrawals',params=base).json()
            self.assertEqual(data['total'],3)
            self.assertEqual(data['summary']['withdrawn'],40)
            self.assertEqual(data['summary']['pending'],135)
            self.assertIsNone(data['summary']['blacklisted'])
            self.assertEqual(data['summary_unavailable']['blacklisted'],'blacklist_source_unverified')
            # Internal-account flags must not be treated as blacklist evidence.
            with SessionLocal() as session:
                session.get(Member,member_ids[0]).is_true=0
                session.commit()
            changed=self.client.get('/api/v1/withdrawals',params=base).json()
            self.assertEqual(changed['summary'],data['summary'])
            with SessionLocal() as session:
                session.get(Member,member_ids[0]).is_true=1
                session.commit()
            data=self.client.get('/api/v1/withdrawals',params={**base,'status':4,'is_true':1}).json()
            self.assertEqual(data['total'],0)
            self.assertEqual(data['summary']['pending'],135)
            data=self.client.get('/api/v1/withdrawals',params={**base,'agent_id':998803,'is_true':1}).json()
            self.assertEqual(data['total'],1)
            self.assertEqual(data['items'][0]['id'],ids[0])
            self.assertEqual(data['summary']['pending'],125)
            self.assertEqual(self.client.get('/api/v1/withdrawals',params={**base,'is_true':2}).status_code,422)
            operator=self.login_headers('operator-test','Operator-Test-123!')
            self.assertEqual(self.client.post('/api/v1/withdrawals/batch-approve',json={'ids':[ids[0]]},headers=operator).status_code,403)
            reviewer=self.login_headers('reviewer-test','Reviewer-Test-123!')
            response=self.client.post('/api/v1/withdrawals/batch-approve',json={'ids':[ids[0],ids[2]]},headers=reviewer)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['updated'],2)
            self.assertTrue(all(row['audit_operator_id'] for row in response.json()['items']))
            transfer=self.client.post('/api/v1/withdrawals/batch-transfer',json={'ids':[ids[0],ids[2]]},headers=reviewer)
            self.assertEqual(transfer.status_code,503)
            with SessionLocal() as session:
                for wid in [ids[0],ids[2]]:
                    item=session.get(Withdrawal,wid)
                    self.assertEqual(item.plan_status,0)
                    self.assertIsNone(item.transferred_at)
                    self.assertEqual(item.transfer_operator_id,0)
            data=self.client.get('/api/v1/withdrawals',params=base).json()
            self.assertEqual(data['summary']['withdrawn'],175)
            self.assertEqual(data['summary']['pending'],0)
            self.assertIsNone(data['summary']['blacklisted'])
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_(ids)))
                session.execute(delete(Member).where(Member.id.in_(member_ids)))
                session.commit()
    def test_statistics_beijing_login_and_daily_series(self) -> None:
        from datetime import UTC
        from unittest.mock import patch
        from app.main_from_txt import Game
        with SessionLocal() as session:
            game = Game(name='Beijing statistics regression')
            session.add(game)
            session.flush()
            gid = game.id
            for index, login in enumerate(['2026-01-31T15:59:59Z', '2026-01-31T16:00:00Z',
                                            '2026-02-01T23:59:59+08:00', '2026-02-01T16:00:00Z',
                                            'invalid', '2026-01-31T16:30:00']):
                session.add(Member(username=f'beijing-{index}', game_id=gid, last_login_time=login,
                                   address='北京市朝阳区' if index == 0 else ('浙江省杭州市' if index == 1 else ''),
                                   created_at=datetime(2026, 1, 31, 16)))
            session.add_all([AdRecord(game_id=gid, estimate_income=3, created_at=datetime(2026,1,31,15,59)),
                             AdRecord(game_id=gid, estimate_income=5, created_at=datetime(2026,1,31,16)),
                             AdRecord(game_id=gid, estimate_income=7, created_at=datetime(2026,2,1,15,59))])
            session.commit()
        try:
            with patch('app.main_from_txt.now', return_value=datetime(2026,2,1,1,tzinfo=UTC)):
                response = self.client.get(f'/api/v1/games/{gid}/statistics')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['today_login'], 3)
            self.assertEqual(data['regions'], [{'name':'北京','value':1},{'name':'浙江','value':1}])
            self.assertEqual(data['today_new'], 6)
            self.assertEqual(data['previous_month_income'], 3)
            self.assertEqual(data['month_income'], 12)
            self.assertEqual(data['income'], [{'date':'2026-01-31','amount':3}, {'date':'2026-02-01','amount':12}])
            self.assertEqual(data['registrations'], [{'date':'2026-02-01','count':6}])
            self.assertEqual(data['metrics'], [
                {'date':'2026-01-31','income':3,'coin':0,'activity':None,'clicks':None},
                {'date':'2026-02-01','income':12,'coin':0,'activity':None,'clicks':None},
            ])
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.game_id == gid))
                session.execute(delete(Member).where(Member.game_id == gid))
                session.execute(delete(Game).where(Game.id == gid))
                session.commit()

    def test_daily_activity_scope_dates_and_pagination(self) -> None:
        from app.main_from_txt import Game, DailyActivity
        with SessionLocal() as session:
            games = [Game(name='activity regression'), Game(name='other activity')]
            session.add_all(games)
            session.flush()
            gids = [game.id for game in games]
            session.add_all([DailyActivity(game_id=gids[0], date=date(2026,1,1), num=8),
                             DailyActivity(game_id=gids[0], date=date(2026,1,2), num=3),
                             DailyActivity(game_id=gids[1], date=date(2026,1,2), num=99)])
            session.commit()
        try:
            path = f'/api/v1/games/{gids[0]}/daily-activity'
            data = self.client.get(path, params={'date_from':'2026-01-02','date_to':'2026-01-02'}).json()
            self.assertEqual(data['total'], 1)
            self.assertEqual(data['items'][0]['num'], 3)
            data = self.client.get(path, params={'sort':'num','order':'asc','offset':1,'limit':1}).json()
            self.assertEqual(data['total'], 2)
            self.assertEqual(data['items'][0]['num'], 8)
            for params in [{'date_from':'2026-01-02','date_to':'2026-01-01'}, {'date_from':'2026-02-30'},
                           {'sort':'game_id'}, {'offset':-1}, {'limit':201}]:
                self.assertEqual(self.client.get(path,params=params).status_code, 422)
            self.assertEqual(self.client.get('/api/v1/games/999999999/daily-activity').status_code,404)
        finally:
            with SessionLocal() as session:
                session.execute(delete(DailyActivity).where(DailyActivity.game_id.in_(gids)))
                session.execute(delete(Game).where(Game.id.in_(gids)))
                session.commit()

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
            self.assertEqual(data['month_income'],1.0);self.assertEqual(data['yesterday_income'],0.0);self.assertEqual(data['year_income'],5.0);self.assertEqual(data['previous_month_income'],4.0)
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
            with SessionLocal() as session:
                session.execute(delete(DailyActivity).where(DailyActivity.game_id.in_(ids)))
                session.execute(delete(AdRecord).where(AdRecord.request_id.like('stats-%')))
                session.execute(delete(Member).where(Member.username=='stats member'))
                session.execute(delete(Game).where(Game.id.in_(ids)))
                session.commit()

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
            with SessionLocal() as session:
                session.get(Member,ids[0]).game_addiction_time='2026-09-17 12:00:00'
                session.get(Member,ids[1]).game_addiction_time='2026-09-16 12:00:00'
                session.commit()
            params={**base,'is_true':0,'game_addiction_enable':1,'created_from':'2025-01-02T00:00:00+08:00','created_to':'2025-01-02T00:00:00+08:00'}
            response=self.client.get('/api/v1/members',params=params)
            self.assertEqual(response.status_code,200)
            self.assertEqual([row['id'] for row in response.json()['items']],[ids[0]])
            for key,value in [('is_true',1),('game_addiction_enable',0)]:
                self.assertEqual(self.client.get('/api/v1/members',params={**params,key:value}).json()['total'],0)
            for field,expected in [('coin',ids[0]),('coin_user',ids[1]),('freeze_coin',ids[1]),('created_at',ids[0]),('game_addiction_time',ids[1])]:
                response=self.client.get('/api/v1/members',params={**base,'sort':field,'order':'asc','limit':1})
                self.assertEqual(response.json()['total'],2)
                self.assertEqual(response.json()['items'][0]['id'],expected)
            response=self.client.get('/api/v1/members',params={**base,'sort':'game_addiction_time','order':'desc','limit':1,'offset':1})
            self.assertEqual(response.json()['items'][0]['id'],ids[1])
            range_query={**base,'game_addiction_time':'2026-09-17 12:00:00 - 2026-09-17 12:00:00'}
            result=self.client.get('/api/v1/members',params=range_query)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual([row['id'] for row in result.json()['items']],[ids[0]])
            self.assertEqual(self.client.get('/api/v1/members',params={**range_query,'game_id':998772}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/members',params={**range_query,'created_from':'2025-01-03T00:00:00+08:00'}).json()['total'],0)
            for bad_range in ['2026-02-30 00:00:00 - 2026-03-01 00:00:00','2026-09-18 00:00:00 - 2026-09-17 00:00:00','2026-09-17','2026-09-17 00:00:00Z - 2026-09-18 00:00:00Z']:
                self.assertEqual(self.client.get('/api/v1/members',params={**base,'game_addiction_time':bad_range}).status_code,422)
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

    def test_ads_sorting_applies_before_pagination(self) -> None:
        from app.main_from_txt import AdRecord
        from datetime import datetime
        with SessionLocal() as session:
            rows=[AdRecord(request_id='sort-fixture-c',ecpm=10,coin=1,estimate_income=20,ad_network_platform_name='B',created_at=datetime(2026,1,1),watched_at=datetime(2026,1,3)),
                  AdRecord(request_id='sort-fixture-a',ecpm=2,coin=100,estimate_income=5,ad_network_platform_name='A',created_at=datetime(2026,1,2)),
                  AdRecord(request_id='sort-fixture-b',ecpm=2,coin=200,estimate_income=15,ad_network_platform_name='C',created_at=datetime(2026,1,4),watched_at=datetime(2026,1,1))]
            session.add_all(rows);session.commit();ids=[r.id for r in rows]
        try:
            orders={'pre_ecpm':[2,1,0],'estimate_income':[1,2,0],
                    'ad_network_platform_name':[1,0,2],'create_time':[2,1,0],'request_id':[1,2,0]}
            for field,indices in orders.items():
                params={'q':'sort-fixture-','sort':field,'order':'asc','limit':1}
                for offset,index in enumerate(indices):
                    response=self.client.get('/api/v1/ads',params={**params,'offset':offset})
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(response.json()['total'],3)
                    self.assertEqual(response.json()['items'][0]['id'],ids[index],field)
                result=self.client.get('/api/v1/ads',params={**params,'order':'desc'}).json()
                self.assertEqual(result['items'][0]['id'],ids[indices[-1]],field)
            self.assertEqual(self.client.get('/api/v1/ads',params={'sort':'invalid'}).status_code,422)
            self.assertEqual(self.client.get('/api/v1/ads',params={'order':'invalid'}).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.id.in_(ids)));session.commit()

    def test_ad_import_rejects_invalid_numbers_without_losing_valid_rows(self) -> None:
        import csv
        from io import StringIO
        prefix = f"numeric-{uuid4().hex}"
        csv_body = StringIO()
        writer = csv.writer(csv_body)
        writer.writerow(['广告request_id', 'user_id', 'coin', 'watched_at'])
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
            self.assertTrue(all('不是有效数字' in error['errors'][0] for error in data['errors']))
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

    def test_ad_import_malformed_files_return_readable_validation_errors(self) -> None:
        for body, message in [(b' ', '不能为空'), (b'\xff', '编码'), (b'request_id,coin\n\"unterminated,1', 'CSV')]:
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
            self.assertEqual(result['summary']['pending'],40.0)
            self.assertEqual(result['summary']['paid'],0.0)
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
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.patch(path, json={'plan_status': 0}).status_code, 200)
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

    def test_subsidy_crud_permissions_atomic_delete_and_audit(self) -> None:
        from app.main_from_txt import AdminOperation, Subsidy
        with SessionLocal() as session:
            rows = [Subsidy(status=0, tx_price=10, price=2, receive_name='Edit recipient', receive_tel='00123'),
                    Subsidy(status=0, tx_price=20, price=4),
                    Subsidy(status=1, tx_price=30, price=6)]
            session.add_all(rows)
            session.commit()
            ids = [row.id for row in rows]
        try:
            operator = self.login_headers('operator-test', 'Operator-Test-123!')
            listing = self.client.get('/api/v1/subsidies')
            self.assertEqual(listing.status_code, 200)
            self.assertEqual(listing.json()['permissions'], dict(edit=True, delete=True, review=True))
            self.assertEqual(self.client.get('/api/v1/subsidies', headers=operator).json()['permissions'],
                             dict(edit=False, delete=False, review=False))
            path = f'/api/v1/subsidies/{ids[0]}'
            changed = self.client.patch(path, json={'price': 3.5, 'pics': 'https://fixture.test/proof.png'})
            self.assertEqual(changed.status_code, 200)
            self.assertEqual(changed.json()['price'], 3.5)
            self.assertEqual(changed.json()['pics'], 'https://fixture.test/proof.png')
            self.assertEqual(self.client.patch(path, json={}, headers=operator).status_code, 403)
            self.assertEqual(self.client.patch(path, json={'price': 5}, headers=operator).status_code, 403)
            self.assertEqual(self.client.patch(path, json={'status': 4, 'sub_msg': ' '}).status_code, 422)
            rejected = self.client.patch(path, json={'status': 4, 'sub_msg': ' rejected by fixture '})
            self.assertEqual(rejected.status_code, 200)
            self.assertEqual(rejected.json()['status'], 2)
            self.assertEqual(rejected.json()['sub_msg'], 'rejected by fixture')
            self.assertTrue(rejected.json()['audit_operator_id'])
            self.assertEqual(self.client.patch(f'/api/v1/subsidies/{ids[2]}', json={'status': 0}).status_code, 409)
            self.assertEqual(self.client.delete(path, headers=operator).status_code, 403)
            self.assertEqual(self.client.delete('/api/v1/subsidies/999999999').status_code, 404)
            self.assertEqual(self.client.post('/api/v1/subsidies/batch-delete', json={'ids': [ids[1], 999999999]}).status_code, 404)
            with SessionLocal() as session:
                self.assertIsNotNone(session.get(Subsidy, ids[1]))
            deleted = self.client.post('/api/v1/subsidies/batch-delete', json={'ids': ids[:2]})
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(deleted.json(), {'deleted': 2})
            with SessionLocal() as session:
                self.assertIsNone(session.get(Subsidy, ids[0]))
                self.assertIsNone(session.get(Subsidy, ids[1]))
                audit = session.scalars(select(AdminOperation).where(AdminOperation.path == '/api/v1/subsidies/batch-delete')).all()
                self.assertEqual(len(audit), 2)
                self.assertTrue(all(entry.admin_id > 0 for entry in audit))
        finally:
            with SessionLocal() as session:
                session.execute(delete(Subsidy).where(Subsidy.id.in_(ids)))
                session.execute(delete(AdminOperation).where(AdminOperation.path == '/api/v1/subsidies/batch-delete'))
                session.commit()

    def test_withdrawal_edit_detail_permissions_and_processed_guard(self) -> None:
        from app.main_from_txt import AdminOperation, Withdrawal
        with SessionLocal() as session:
            pending = Withdrawal(status=0, good_name='Fixture product', receive_name='Recipient',
                                 receive_tel='00123', exchange_value=125, exchange_type=1)
            processed = Withdrawal(status=1, good_name='Processed product')
            session.add_all([pending, processed])
            session.commit()
            pending_id, processed_id = pending.id, processed.id
        try:
            operator = self.login_headers('operator-test', 'Operator-Test-123!')
            data = self.client.get(f'/api/v1/withdrawals/{pending_id}')
            self.assertEqual(data.status_code, 200)
            self.assertEqual(data.json()['good_name'], 'Fixture product')
            self.assertEqual(self.client.get('/api/v1/withdrawals').json()['permissions'],
                             dict(edit=True, review=True, row_review=False, transfer=True, blacklist=True))
            self.assertEqual(self.client.get('/api/v1/withdrawals', headers=operator).json()['permissions'],
                             dict(edit=False, review=False, row_review=False, transfer=False, blacklist=False))
            self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{pending_id}',
                                               json={'good_name': 'Updated product', 'exchange_value': 130}).status_code, 200)
            self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{pending_id}',
                                               json={'exchange_value': -1}).status_code, 422)
            self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{pending_id}',
                                               json={'exchange_type': 9}).status_code, 422)
            self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{pending_id}',
                                               json={'good_name': 'x'}, headers=operator).status_code, 403)
            self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{processed_id}',
                                               json={'good_name': 'blocked'}).status_code, 409)
            with SessionLocal() as session:
                entries = session.scalars(select(AdminOperation).where(
                    AdminOperation.path == f'/api/v1/withdrawals/{pending_id}')).all()
                self.assertEqual(len(entries), 1)
                self.assertEqual(session.get(Withdrawal, processed_id).good_name, 'Processed product')
        finally:
            with SessionLocal() as session:
                session.execute(delete(Withdrawal).where(Withdrawal.id.in_([pending_id, processed_id])))
                session.execute(delete(AdminOperation).where(AdminOperation.path == f'/api/v1/withdrawals/{pending_id}'))
                session.commit()

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

    def test_coin_log_name_search_sort_summary_and_hidden_status(self) -> None:
        from app.main_from_txt import CoinLog, Game
        with SessionLocal() as session:
            agents=[Agent(name='ledger agent 100%_',user_name='ledger-agent-a',game_ad_status=0),
                    Agent(name='ledger agent 100XX',user_name='ledger-agent-b',game_ad_status=1)]
            session.add_all(agents);session.flush();agent_ids=[item.id for item in agents]
            games=[Game(name='ledger exact',agent_id=agent_ids[0]),Game(name='ledger exact suffix',agent_id=agent_ids[1])]
            session.add_all(games);session.flush();game_ids=[item.id for item in games]
            logs=[CoinLog(user_id=695016,agent_id=agent_ids[0],game_id=game_ids[0],coin=12.5,remark='ledger-name-contract'),
                  CoinLog(user_id=695016,agent_id=agent_ids[0],game_id=game_ids[0],coin=-2.5,remark='ledger-name-contract'),
                  CoinLog(user_id=695016,agent_id=agent_ids[1],game_id=game_ids[1],coin=100,remark='ledger-name-contract')]
            session.add_all(logs);session.commit();log_ids=[item.id for item in logs]
        try:
            base={'remark':'ledger-name-contract'}
            response=self.client.get('/api/v1/coin-logs',params={**base,'game_name_exact':'ledger exact','sort':'coin','order':'asc','limit':1})
            self.assertEqual(response.status_code,200)
            data=response.json();self.assertEqual(data['total'],2);self.assertEqual(data['summary']['change'],10)
            self.assertEqual(data['items'][0]['coin'],-2.5);self.assertEqual(data['items'][0]['game_ad_status'],0)
            data=self.client.get('/api/v1/coin-logs',params={**base,'agent_name':'100%_'}).json()
            self.assertEqual(data['total'],2);self.assertEqual(data['summary']['change'],10)
            self.assertEqual(self.client.get('/api/v1/coin-logs',params={**base,'game_name_exact':'ledger exact','game_id':game_ids[1]}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/coin-logs',params={**base,'agent_name':'100%_','agent_id':agent_ids[1]}).json()['total'],0)
            data=self.client.get('/api/v1/coin-logs',params={**base,'game_ad_status':1}).json()
            self.assertEqual(data['items'][0]['game_ad_status'],1);self.assertEqual(data['summary']['change'],100)
            self.assertEqual(self.client.get('/api/v1/coin-logs',params={**base,'game_name':'ledger exact'}).json()['total'],3)
        finally:
            with SessionLocal() as session:
                session.execute(delete(CoinLog).where(CoinLog.id.in_(log_ids)))
                session.execute(delete(Game).where(Game.id.in_(game_ids)))
                session.execute(delete(Agent).where(Agent.id.in_(agent_ids)));session.commit()

    def test_risk_history_names_scope_and_related_columns(self) -> None:
        from app.main_from_txt import Game, RiskRecord
        with SessionLocal() as session:
            agents=[Agent(name='risk agent 100%_',user_name='risk-name-agent'),Agent(name='risk agent 100XXa',user_name='risk-name-other')]
            session.add_all(agents);session.flush();aids=[a.id for a in agents]
            games=[Game(name='risk exact',agent_id=aids[0]),Game(name='risk exact suffix',agent_id=aids[1])]
            session.add_all(games);session.flush();gids=[g.id for g in games]
            member=Member(username='risk name %_',parent_id=987654);session.add(member);session.flush();uid=member.id
            events=[RiskRecord(user_id=uid,game_id=gids[i%2],agent_id=aids[i%2],tagcode='risk-name-'+str(i),hardware_main_id='device%_',
                               created_at=datetime(2026,9,17,16,0,2-i)) for i in range(3)]
            session.add_all(events);session.commit();ids=[r.id for r in events]
        try:
            path='/api/v1/risk/history';base={'q':'risk-name-'}
            response=self.client.get(path,params={**base,'sort':'created_at','order':'asc','limit':1})
            self.assertEqual(response.status_code,200);self.assertEqual(response.json()['total'],3)
            row=response.json()['items'][0];self.assertEqual(row['id'],ids[2]);self.assertEqual(row['parent_id'],987654)
            self.assertEqual(row['username'],'risk name %_');self.assertEqual(row['agent_name'],'risk agent 100%_')
            for filters,count in [({'game_name_exact':'risk exact'},2),({'game_name':'risk exact'},3),
                                  ({'game_name_exact':'risk exact','game_id':gids[1]},0),
                                  ({'agent_name':'100%_'},2),({'agent_name':'100%_','agent_id':aids[1]},0),
                                  ({'parent_id':987654,'username':'%_','hardware_main_id':'%_'},3),
                                  ({'member_id':uid,'user_id':str(uid),'game_name_exact':'risk exact'},2),
                                  ({'member_id':uid+1000,'game_name_exact':'risk exact'},0)]:
                with self.subTest(filters=filters):self.assertEqual(self.client.get(path,params={**base,**filters}).json()['total'],count)
            data=self.client.get(path,params={**base,'created_from':'2026-09-18T00:00:01+08:00','created_to':'2026-09-18T00:00:02+08:00'}).json()
            self.assertEqual({r['id'] for r in data['items']},{ids[0],ids[1]})
            for filters in [{'sort':'risk_score'},{'order':'invalid'},{'created_from':'2026-09-19T00:00:00Z','created_to':'2026-09-18T00:00:00Z'}]:
                self.assertEqual(self.client.get(path,params=filters).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(RiskRecord).where(RiskRecord.id.in_(ids)));session.execute(delete(Member).where(Member.id==uid))
                session.execute(delete(Game).where(Game.id.in_(gids)));session.execute(delete(Agent).where(Agent.id.in_(aids)));session.commit()

    def test_whitelist_names_sort_dates_and_fixed_membership(self) -> None:
        from app.main_from_txt import Game
        with SessionLocal() as session:
            agent=Agent(name='white agent 100%_',user_name='white-agent-contract');session.add(agent);session.flush();aid=agent.id
            games=[Game(name='white exact',agent_id=aid),Game(name='white exact suffix',agent_id=aid)]
            session.add_all(games);session.flush();gids=[g.id for g in games]
            parent=Member(username='white-parent-contract',name='Fixture Parent');session.add(parent);session.flush();pid=parent.id
            members=[Member(username='white-query-'+str(i),name='white name '+str(i),parent_id=pid,game_id=gids[i%2],agent_id=aid,
                            is_white=0 if i==3 else 1,status=i%2,coin=30-i,freeze_coin=i,coin_user=i*10,
                            created_at=datetime(2026,9,17,16,0,i)) for i in range(4)]
            session.add_all(members);session.commit();ids=[m.id for m in members]
        try:
            base={'username':'white-query'}
            data=self.client.get('/api/v1/risk/whitelist',params={**base,'sort':'coin','order':'asc','limit':1}).json()
            self.assertEqual(data['total'],3);self.assertEqual(data['items'][0]['id'],ids[2])
            row=data['items'][0];self.assertEqual(row['parent_username'],'white-parent-contract');self.assertEqual(row['parent_name'],'Fixture Parent');self.assertEqual(row['agent_name'],'white agent 100%_')
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params={**base,'game_name':'white exact'}).json()['total'],2)
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params={**base,'game_name':'white exact','game_id':gids[1]}).json()['total'],0)
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params={**base,'agent_name':'100%_'}).json()['total'],3)
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params={**base,'agent_name':'100%_','agent_id':aid+1000}).json()['total'],0)
            data=self.client.get('/api/v1/risk/whitelist',params={**base,'created_from':'2026-09-18T00:00:01+08:00','created_to':'2026-09-18T00:00:02+08:00'}).json()
            self.assertEqual({r['id'] for r in data['items']},{ids[1],ids[2]})
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params={**base,'is_white':0}).json()['total'],3)
            for params in [{'created_from':'2026-09-19T00:00:00Z','created_to':'2026-09-18T00:00:00Z'},{'sort':'username'},{'order':'invalid'}]:
                self.assertEqual(self.client.get('/api/v1/risk/whitelist',params=params).status_code,422)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids+[pid])));session.execute(delete(Game).where(Game.id.in_(gids)))
                session.execute(delete(Agent).where(Agent.id==aid));session.commit()

    def test_whitelist_switch_permissions_and_removal(self) -> None:
        with SessionLocal() as session:
            member=Member(username='white-lifecycle',is_white=1,status=1,coin=15,freeze_coin=2)
            session.add(member);session.commit();uid=member.id
        try:
            path=f'/api/v1/members/{uid}';query={'username':'white-lifecycle'}
            risk=self.login_headers('risk-test','Risk-Test-123!');operator=self.login_headers('operator-test','Operator-Test-123!')
            self.assertEqual(self.client.patch(path,json={'status':0},headers=risk).status_code,403)
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params=query).json()['items'][0]['status'],1)
            self.assertEqual(self.client.patch(path,json={'status':0},headers=operator).status_code,200)
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params={**query,'status':1}).json()['total'],0)
            self.assertEqual(self.client.patch(path,json={'is_white':0},headers=risk).status_code,200)
            self.assertEqual(self.client.get('/api/v1/risk/whitelist',params=query).json()['total'],0)
            with SessionLocal() as session:
                row=session.get(Member,uid);self.assertEqual((row.coin,row.freeze_coin,row.status),(15,2,0))
        finally:
            with SessionLocal() as session:session.execute(delete(Member).where(Member.id==uid));session.commit()

    def test_reference_ad_filter_contract(self) -> None:
        with SessionLocal() as session:
            records=[AdRecord(request_id='contract-check-a', parent_id=0, user_id=8123, coin=100, estimate_income=2, is_fu=1, fu_type=3, is_look=0),
                     AdRecord(request_id='contract-check-b', parent_id=8123, user_id=81230, coin=2, estimate_income=100, is_fu=0, fu_type=1, is_look=1)]
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
            self.assertIn('金币', exported.text.splitlines()[0])
            self.assertIn(',2.0,', exported.text)
            self.assertEqual(result.json()['summary']['coin'], 2.0)
            for field,value in [('parent_id',0),('user_id',8123)]:
                search={'q':'contract-check',field:value}
                filtered=self.client.get('/api/v1/ads',params=search)
                self.assertEqual(filtered.status_code,200)
                self.assertEqual([row['id'] for row in filtered.json()['items']],[ids[0]])
                exported=self.client.get('/api/v1/ads/export',params=search)
                self.assertEqual(exported.status_code,200)
                self.assertIn('contract-check-a',exported.text)
                self.assertNotIn('contract-check-b',exported.text)
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.id.in_(ids)));session.commit()

    def test_ad_name_search_and_export(self) -> None:
        from app.main_from_txt import Game, Agent
        with SessionLocal() as session:
            games=[Game(name='ad-name-game'),Game(name='ad-name-game-extra')]
            agents=[Agent(name='ad-name-100%_a'),Agent(name='ad-name-100XXa')]
            session.add_all(games+agents);session.flush()
            gids=[x.id for x in games];aids=[x.id for x in agents]
            rows=[AdRecord(request_id='ad-name-a',game_id=gids[0],agent_id=aids[0],game_name='stale name'),
                  AdRecord(request_id='ad-name-b',game_id=gids[1],agent_id=aids[1])]
            session.add_all(rows);session.commit();ids=[x.id for x in rows]
        try:
            for filters in [{'game_name':'ad-name-game'},{'agent_name':'100%_'},{'game_name':'ad-name-game','agent_name':'100%_'}]:
                params={'q':'ad-name-',**filters}
                response=self.client.get('/api/v1/ads',params=params)
                self.assertEqual(response.status_code,200)
                self.assertEqual([x['id'] for x in response.json()['items']],[ids[0]])
                self.assertEqual(response.json()['items'][0]['game_name'],'ad-name-game')
                self.assertEqual(response.json()['items'][0]['agent_name'],'ad-name-100%_a')
                exported=self.client.get('/api/v1/ads/export',params=params)
                self.assertEqual(exported.status_code,200)
                self.assertIn('ad-name-a',exported.text)
                self.assertNotIn('ad-name-b',exported.text)
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdRecord).where(AdRecord.id.in_(ids)))
                session.execute(delete(Game).where(Game.id.in_(gids)))
                session.execute(delete(Agent).where(Agent.id.in_(aids)))
                session.commit()

    def test_tutorial_catalog_pagination_dates_detail_and_authentication(self) -> None:
        import json
        from datetime import UTC
        from unittest.mock import patch
        start = int(datetime(2040, 1, 1, 16, tzinfo=UTC).timestamp())
        rows = [{'id': i+1, 'name': 'Fixture <>& '+str(i), 'content': '<p>Body '+str(i)+'</p>',
                 'create_time': start+(i % 3)*60, 'update_time': start+(i % 2)*86400} for i in range(225)]
        rows.append({'id': 999, 'name': 'No date', 'content': '', 'create_time': 0, 'update_time': 0})
        with tempfile.TemporaryDirectory() as directory, patch('app.main_from_txt.PUBLIC_DIR', Path(directory)):
            source = Path(directory)/'target-book.json'; source.write_text(json.dumps({'rows': rows}), encoding='utf-8')
            path = '/api/v1/tutorials'
            self.assertEqual(self.client.get(path, headers={'Authorization': ''}).status_code, 401)
            self.assertEqual(self.client.get(path+'/1', headers={'Authorization': ''}).status_code, 401)
            self.assertEqual(self.client.get(path+'/99999').status_code, 404)
            detail = self.client.get(path+'/1').json()
            self.assertEqual(detail['content'], rows[0]['content']); self.assertEqual(detail['name'], rows[0]['name'])
            params = {'sort': 'created_at', 'order': 'asc', 'limit': 200}
            a = self.client.get(path, params=params).json(); b = self.client.get(path, params={**params, 'offset': 200}).json()
            expected = [999]+[r['id'] for r in sorted(rows[:225], key=lambda row: (row['create_time'], -row['id']))]
            self.assertEqual(a['total'], 226); self.assertEqual(b['total'], 226)
            self.assertEqual([row['id'] for row in a['items']+b['items']], expected)
            self.assertTrue(all('content' not in row for row in a['items']))
            self.assertIsNone(self.client.get(path+'/999').json()['created_at'])
            params = {'created_from': '2040-01-02T00:01:00+08:00', 'created_to': '2040-01-02T00:01:00+08:00',
                      'updated_from': '2040-01-03T00:00:00+08:00', 'sort': 'updated_at', 'order': 'desc', 'limit': 200}
            filtered = self.client.get(path, params=params).json()
            expected = [row['id'] for row in reversed(rows[:225]) if row['create_time'] == start+60 and row['update_time'] == start+86400]
            self.assertEqual([row['id'] for row in filtered['items']], expected)
            for invalid in [{'sort': 'name'}, {'order': 'wrong'}, {'limit': 201}, {'offset': -1},
                            {'created_from': 'bad'}, {'updated_from': '2040-01-02', 'updated_to': '2040-01-01'}]:
                self.assertEqual(self.client.get(path, params=invalid).status_code, 422)
            risk = self.login_headers('risk-test', 'Risk-Test-123!')
            self.assertEqual(self.client.get(path, headers=risk).status_code, 200)

    def test_tutorial_catalog_failure_and_empty_are_distinct(self) -> None:
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory, patch('app.main_from_txt.PUBLIC_DIR', Path(directory)):
            source = Path(directory)/'target-book.json'; path = '/api/v1/tutorials'
            self.assertEqual(self.client.get(path).status_code, 503)
            for content in ['invalid json', '[]', '{}', '{"rows":null}', json.dumps({'rows': [{'id': 1}]}),
                            json.dumps({'rows': [{'id': 1, 'name': 'A'}, {'id': 1, 'name': 'B'}]})]:
                source.write_text(content, encoding='utf-8')
                self.assertEqual(self.client.get(path).status_code, 503)
                self.assertEqual(self.client.get(path+'/1').status_code, 503)
            source.write_text(json.dumps({'items': []}), encoding='utf-8')
            self.assertEqual(self.client.get(path).json()['total'], 0)

    def test_profile_avatar_upload_save_and_validation(self) -> None:
        from io import BytesIO
        from unittest.mock import patch
        from PIL import Image, PngImagePlugin
        headers = self.login_headers('risk-test', 'Risk-Test-123!')
        before = self.client.get('/api/auth/me', headers=headers).json()
        output = BytesIO(); metadata = PngImagePlugin.PngInfo(); metadata.add_text('private', 'must be removed')
        Image.new('RGB', (9, 7), (40, 160, 100)).save(output, format='PNG', pnginfo=metadata)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'MEMBER_IMAGE_DIR': directory}):
            try:
                uploaded = self.client.post('/api/auth/avatar', content=output.getvalue(), headers=headers)
                self.assertEqual(uploaded.status_code, 201, uploaded.text)
                url = uploaded.json()['url']
                self.assertRegex(url, r'^/api/member-images/[0-9a-f]{48}\.png$')
                self.assertEqual(self.client.get('/api/auth/me', headers=headers).json()['avatar'], before['avatar'])
                fetched = self.client.get(url, headers={'Authorization': ''})
                self.assertEqual(fetched.status_code, 200)
                self.assertEqual(fetched.headers['x-content-type-options'], 'nosniff')
                with Image.open(BytesIO(fetched.content)) as image:
                    self.assertEqual(image.size, (9, 7)); self.assertEqual(image.getpixel((0, 0)), (40, 160, 100, 255))
                    self.assertNotIn('private', image.info)
                body = {'display_name': 'Avatar fixture', 'avatar': url}
                saved = self.client.patch('/api/auth/me', json=body, headers=headers)
                self.assertEqual(saved.status_code, 200, saved.text)
                fresh = self.login_headers('risk-test', 'Risk-Test-123!')
                self.assertEqual(self.client.get('/api/auth/me', headers=fresh).json()['avatar'], url)
                self.assertEqual(self.client.patch('/api/auth/me', json={'display_name': 'Keep avatar'}, headers=headers).json()['avatar'], url)
                for invalid in ['https://example.com/a.png', 'javascript:alert(1)', '', '/api/member-images/'+'0'*48+'.png', '/api/member-images/../../test.png']:
                    self.assertEqual(self.client.patch('/api/auth/me', json={**body, 'avatar': invalid}, headers=headers).status_code, 422)
                    self.assertEqual(self.client.get('/api/auth/me', headers=headers).json()['avatar'], url)
                for content in [b'<svg/>', b'\x89PNG\r\n\x1a\n']:
                    self.assertEqual(self.client.post('/api/auth/avatar', content=content, headers=headers).status_code, 422)
                large = BytesIO(); Image.new('RGB', (4097, 1)).save(large, format='PNG')
                self.assertEqual(self.client.post('/api/auth/avatar', content=large.getvalue(), headers=headers).status_code, 422)
                self.assertEqual(self.client.post('/api/auth/avatar', content=b'x'*(2*1024*1024+1), headers=headers).status_code, 413)
                self.assertEqual(self.client.post('/api/auth/avatar', content=output.getvalue(), headers={'Authorization': ''}).status_code, 401)
                self.assertEqual(len(list(Path(directory).iterdir())), 1)
            finally:
                self.client.patch('/api/auth/me', json={'display_name': before['display_name'], 'avatar': before['avatar']}, headers=headers)

    def test_profile_password_roundtrip(self) -> None:
        from app.main_from_txt import AdminOperation
        username = 'profile-password-'+uuid4().hex
        old_password = 'Original-Password-123!'; new_password = 'Changed-Password-456!'
        with SessionLocal() as session:
            hashed, salt = hash_password(old_password)
            user = AdminUser(username=username, display_name='Fixture', password_hash=hashed, password_salt=salt, role='risk', status=1)
            session.add(user); session.commit(); uid = user.id
        try:
            headers = self.login_headers(username, old_password)
            self.assertEqual(self.client.patch('/api/auth/me', json={'display_name': 'Updated', 'password': new_password}, headers=headers).status_code, 200)
            self.assertEqual(self.client.post('/api/auth/login', json={'username': username, 'password': old_password}).status_code, 401)
            fresh = self.login_headers(username, new_password)
            self.assertEqual(self.client.get('/api/auth/me', headers=fresh).json()['display_name'], 'Updated')
            self.assertEqual(self.client.patch('/api/auth/me', json={'display_name': 'Updated', 'password': ''}, headers=fresh).status_code, 200)
            self.login_headers(username, new_password)
        finally:
            with SessionLocal() as session:
                session.execute(delete(AdminOperation).where(AdminOperation.admin_id == uid))
                session.execute(delete(AdminUser).where(AdminUser.id == uid)); session.commit()

    def test_profile_operation_sort_pagination_and_private_scope(self) -> None:
        from datetime import timedelta
        from app.main_from_txt import AdminOperation
        uid = self.client.get('/api/auth/me').json()['id']; prefix = uuid4().hex
        with SessionLocal() as session:
            other = session.scalar(select(AdminUser.id).where(AdminUser.username == 'risk-test'))
            entries = [AdminOperation(admin_id=uid, title=prefix+' <>& '+str(i), path='/fixture/profile', ip='192.0.2.1',
                created_at=datetime(2040, 1, 1)+timedelta(minutes=i % 3)) for i in range(225)]
            entries.append(AdminOperation(admin_id=other, title=prefix+' private', path='/fixture/profile', ip='192.0.2.2'))
            session.add_all(entries); session.commit(); ids = [row.id for row in entries]
        try:
            expected = sorted(range(225), key=lambda i: (i % 3, -ids[i]))
            params = {'q': prefix, 'limit': 200, 'sort': 'created_at', 'order': 'asc'}
            first = self.client.get('/api/auth/operations', params=params).json()
            second = self.client.get('/api/auth/operations', params={**params, 'offset': 200}).json()
            self.assertEqual(first['total'], 225); self.assertEqual(second['total'], 225)
            self.assertEqual([row['id'] for row in first['items']+second['items']], [ids[i] for i in expected])
            default = self.client.get('/api/auth/operations', params={'q': prefix}).json()
            self.assertEqual([row['id'] for row in default['items']], list(reversed(ids[:225]))[:10])
            special = self.client.get('/api/auth/operations', params={'q': prefix+' <>&'}).json()
            self.assertEqual(special['total'], 225)
            risk = self.login_headers('risk-test', 'Risk-Test-123!')
            private = self.client.get('/api/auth/operations', params={'q': prefix}, headers=risk).json()
            self.assertEqual([row['id'] for row in private['items']], [ids[-1]])
            for invalid in [{'sort': 'title'}, {'order': 'invalid'}, {'limit': 201}, {'offset': -1}]:
                self.assertEqual(self.client.get('/api/auth/operations', params=invalid).status_code, 422)
        finally:
            with SessionLocal() as session: session.execute(delete(AdminOperation).where(AdminOperation.id.in_(ids))); session.commit()

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

    def test_member_reference_exact_game_and_ip_filters(self) -> None:
        from app.main_from_txt import Game
        with SessionLocal() as session:
            games=[Game(name='exact-filter-game'),Game(name='exact-filter-game-extra')]
            session.add_all(games);session.flush();gids=[g.id for g in games]
            members=[Member(username='exact-filter-a',game_id=gids[0],ip='192.0.2.1'),
                     Member(username='exact-filter-b',game_id=gids[1],ip='192.0.2.10'),
                     Member(username='exact-filter-c',game_id=gids[0],ip='192.0.2.10')]
            session.add_all(members);session.commit();ids=[m.id for m in members]
        try:
            def query(**params):
                response=self.client.get('/api/v1/members',params={'username':'exact-filter-',**params})
                self.assertEqual(response.status_code,200)
                return response.json()
            self.assertEqual(query()['total'],3)  # Account filtering remains LIKE.
            self.assertEqual(query(game_name='exact-filter-game')['total'],2)
            self.assertEqual(query(game_name='exact-filter')['total'],0)
            self.assertEqual(query(ip='192.0.2.1')['total'],1)
            self.assertEqual(query(ip='192.0.2.')['total'],0)
            self.assertEqual(query(game_name='exact-filter-game',ip='192.0.2.10')['items'][0]['id'],ids[2])
            self.assertEqual(query(game_name='exact-filter-game',ip='192.0.2.1',limit=1)['total'],1)
        finally:
            with SessionLocal() as session:
                session.execute(delete(Member).where(Member.id.in_(ids)))
                session.execute(delete(Game).where(Game.id.in_(gids)));session.commit()

    def test_member_registration_filters(self) -> None:
        with SessionLocal() as session:
            # UTC storage instants for Jan 10 midnight, day end and Jan 11 midnight in Beijing.
            items = [Member(username='registration-check-a', ip='192.0.2.1', last_login_ip='198.51.100.1', created_at=datetime(2026, 1, 9, 16, 0)),
                     Member(username='registration-check-b', ip='192.0.2.2', created_at=datetime(2026, 1, 10, 15, 59, 59)),
                     Member(username='registration-check-c', ip='192.0.2.1', created_at=datetime(2026, 1, 10, 16, 0))]
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
            self.assertEqual(query(create_time='2026-01-10 00:00:00 - 2026-01-10 23:59:59'), 2)
            self.assertEqual(query(create_time='2026-01-10 23:59:59 - 2026-01-10 23:59:59'), 1)
            self.assertEqual(query(create_time='2026-01-11 00:00:00 - 2026-01-11 00:00:00'), 1)
            for invalid in ['2026-01-10 - 2026-01-10 23:59:59', '2026-01-11 00:00:00 - 2026-01-10 00:00:00']:
                self.assertEqual(self.client.get('/api/v1/members',params={'create_time':invalid}).status_code,422)
            self.assertEqual(query(ip='198.51.100.1'), 0)
            self.assertEqual(query(ip='%'), 0)
            for value in ['invalid', '2026-01-11 - 2026-01-10', '9999-12-31', '0001-01-01']:
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

    def test_agent_editor_fields_parent_cycle_and_password_preservation(self) -> None:
        password = "Agent-Editor-Password-123"
        parent = self.client.post(
            "/api/v1/agents",
            json={"name": "agent-editor-parent", "user_name": "agent-editor-parent-user", "password": password},
        )
        self.assertEqual(parent.status_code, 201, parent.text)
        parent_id = parent.json()["id"]
        child = self.client.post(
            "/api/v1/agents",
            json={"parent_id": parent_id, "name": "agent-editor-child"},
        )
        self.assertEqual(child.status_code, 201, child.text)
        child_id = child.json()["id"]
        try:
            detail = self.client.get(f"/api/v1/agents/{parent_id}")
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertEqual(detail.json()["user_name"], "agent-editor-parent-user")
            self.assertNotIn("password", detail.json())
            self.assertNotIn("salt", detail.json())

            with SessionLocal() as session:
                stored = session.get(Agent, parent_id)
                stored_hash = stored.password
                stored_salt = stored.salt
            update = self.client.patch(f"/api/v1/agents/{parent_id}", json={"name": "agent-editor-parent-renamed"})
            self.assertEqual(update.status_code, 200, update.text)
            with SessionLocal() as session:
                stored = session.get(Agent, parent_id)
                self.assertEqual(stored.password, stored_hash)
                self.assertEqual(stored.salt, stored_salt)

            cycle = self.client.patch(f"/api/v1/agents/{parent_id}", json={"parent_id": child_id})
            self.assertEqual(cycle.status_code, 422, cycle.text)
            blank = self.client.post("/api/v1/agents", json={"name": "   "})
            self.assertEqual(blank.status_code, 422, blank.text)
            invalid_flag = self.client.post("/api/v1/agents", json={"name": "agent-editor-invalid", "status": 2})
            self.assertEqual(invalid_flag.status_code, 422, invalid_flag.text)
        finally:
            self.assertEqual(self.client.delete(f"/api/v1/agents/{child_id}").status_code, 204)
            self.assertEqual(self.client.delete(f"/api/v1/agents/{parent_id}").status_code, 204)

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

