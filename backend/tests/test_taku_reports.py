"""Report revisions, ambiguity and thresholds must never mutate balances."""
import unittest
import json
import urllib.error
from unittest.mock import patch
from datetime import timedelta
from decimal import Decimal
import test_member_policy as fixtures
from app import main_from_txt as m
from app import taku_reports as reports
from app import taku_report_sync as sync

HEADER = 'user_id,placement_id,network_firm_id,impression,revenue,currency,cny_estimate_revenue,oaid\n'


class ReportTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def test_report_missing_placement_and_inactive_days(self):
        day=reports.date(2026,10,20)
        rows=reports.parse_report(HEADER+'1,a,28,3,0.9,CNY,1,x\n')
        with self.factory() as s:
            s.get(m.Member,1).created_at=reports.datetime(2026,10,18,6)
            s.add(reports.ReportBatch(game_id=1,day=str(day),digest='fixture',stage='rechecked',
                rows_json=json.dumps(rows),admin_id=0));s.commit()
        local={('1',p,c):{'count':3,'revenue':Decimal(1),'missing':False}
            for p in ('a','b') for c in ('CNY','USD')}
        with patch.object(reports,'local_estimates',return_value=local):
            result=reports.results(1,day)
        item={'id':999,'game_id':1,'user_id':1,'created_at':'2026-10-21T10:00:00+08:00'}
        with self.factory() as s, patch.object(reports,'results',return_value=result):
            reports.withdrawal_checks(s,[item])
            self.assertEqual(item['reconciliation']['missing_placements'],['b'])
            self.assertIsNone(item['reconciliation']['difference_rate'])
        local={key:value for key,value in local.items() if key[1]=='a'}
        with patch.object(reports,'local_estimates',return_value=local):
            result=reports.results(1,day)
        inactive={'status':'rechecked','items':[],'local_placements':{}}
        with self.factory() as s:
            with patch.object(reports,'results',side_effect=lambda game,d: result if d==day else inactive):
                reports.withdrawal_checks(s,[item],period=True)
            self.assertEqual(item['reconciliation']['classification'],'normal')
            self.assertEqual(item['reconciliation']['no_activity_days'],['2026-10-19'])
            self.assertEqual(Decimal(item['reconciliation']['difference_rate']),10)
            with patch.object(reports,'results',side_effect=lambda game,d: result if d==day else {'status':'waiting_report','items':[]}):
                reports.withdrawal_checks(s,[item],period=True)
            self.assertEqual(item['reconciliation']['classification'],'pending')
            self.assertEqual(item['reconciliation']['missing_days'],['2026-10-19'])

    def test_period_covers_complete_days_and_missing_day_blocks_normal(self):
        with self.factory() as s:
            s.get(m.Member,1).created_at=reports.datetime(2026,10,18,6)
            s.commit()
            row={'member_id':1,'currency':'CNY','backend_estimate':'10','backend_complete':True,
                'backend_impressions':10,'impressions':10,'status':'normal','revenue':'9','flagged':False}
            def result(game,day):
                return {'status':'rechecked','items':[row] if str(day)!='2026-10-20' else []}
            item={'id':999,'game_id':1,'user_id':1,'created_at':'2026-10-22T10:00:00+08:00'}
            with patch.object(reports,'results',side_effect=result):
                reports.withdrawal_checks(s,[item],period=True)
            check=item['reconciliation']
            self.assertEqual(check['start_day'],'2026-10-19')
            self.assertEqual(check['end_day'],'2026-10-21')
            self.assertEqual(check['missing_days'],['2026-10-20'])
            self.assertEqual(check['classification'],'pending')
            self.assertIsNone(check['difference_rate'])
            withdrawal=m.Withdrawal(id=1,user_id=1,game_id=1,status=1,
                transferred_at=reports.datetime(2026,10,20,2))
            s.add(withdrawal)
            s.add(m.payouts.Payout(withdrawal_id=1,member_id=1,game_id=1,request_key='period',
                amount_cents=10,coin_cost=1,account='test',real_name='test',out_biz_no='period',state='succeeded'))
            s.commit()
            with patch.object(reports,'results',side_effect=result):
                reports.withdrawal_checks(s,[item],period=True)
            self.assertEqual(item['reconciliation']['start_day'],'2026-10-21')
            self.assertEqual(item['reconciliation']['classification'],'normal')
            self.assertEqual(Decimal(item['reconciliation']['difference_rate']),10)

    def test_withdrawal_local_completeness_currency_and_threshold(self):
        row={'member_id':1,'currency':'CNY','backend_estimate':'10','backend_complete':True,
             'backend_impressions':10,'impressions':10,'status':'normal','revenue':'7','flagged':False}
        report={'status':'rechecked','rule':{'threshold_percent':'20'},'items':[row]}
        with self.factory() as s, patch.object(reports,'results',return_value=report):
            def check():
                item={'game_id':1,'user_id':1,'created_at':'2026-10-22T00:30:00+08:00'}
                reports.withdrawal_checks(s,[item]);return item['reconciliation']
            result=check()
            self.assertEqual(result['day'],'2026-10-21')
            self.assertEqual(result['classification'],'review')
            self.assertEqual(Decimal(result['difference']),3)
            row['backend_complete']=False
            self.assertEqual(check()['classification'],'pending')
            self.assertIsNone(check()['difference'])
            row['backend_complete']=True;report['items'].append({**row,'currency':'USD'})
            self.assertEqual(check()['classification'],'pending')

    def test_threshold_currency_missing_and_shared_devices(self):
        rows = reports.parse_report(HEADER+'1,p,28,10,8,CNY,10,a\n2,p,28,10,7.99,CNY,10,b\n3,p,28,10,0,CNY,,c\n4,p,28,10,0,CNY,10,b\n')
        result = reports.evaluate(rows, {1,2,3,4}, reports.RuleInput(), 'rechecked')
        self.assertEqual([r['status'] for r in result], ['normal','shared_device_review','missing_estimate','shared_device_review'])
        self.assertFalse(any(r['flagged'] for r in result))
        rows = reports.parse_report(HEADER+'1,p,28,10,7.99,CNY,10,a\n')
        self.assertTrue(reports.evaluate(rows,{1},reports.RuleInput(),'preliminary')[0]['flagged'])
        self.assertEqual(reports.evaluate(rows,set(),reports.RuleInput(),'rechecked')[0]['status'],'unmatched')
        with self.assertRaises(m.HTTPException): reports.parse_report(HEADER+'1,p,28,10,NaN,CNY,10,a\n')

    def test_import_revision_access_and_no_wallet_changes(self):
        day=str(reports.datetime.now(reports.CN).date()-timedelta(days=3))
        path='/api/v1/games/1/taku-reports'
        headers=self.admin_headers()
        self.client.put(path+'/rule',json={'basis':'taku_estimate'},headers=headers)
        self.assertEqual(self.client.get(path+'?day='+day,headers=headers).json()['status'],'waiting_report')
        body={'day':day,'csv_text':HEADER+'1,p,28,10,7,CNY,10,a\n','stage':'rechecked'}
        self.assertEqual(self.client.post(path+'/import',json=body).status_code,401)
        first=self.client.post(path+'/import',json=body,headers=headers)
        self.assertEqual(first.status_code,200,first.text)
        self.assertFalse(self.client.post(path+'/import',json=body,headers=headers).json()['imported'])
        result=self.client.get(path+'?day='+day,headers=headers).json()
        self.assertEqual(result['flagged_members'],[1])
        body['csv_text']=HEADER+'1,p,28,10,9,CNY,10,a\n'
        self.assertTrue(self.client.post(path+'/import',json=body,headers=headers).json()['imported'])
        self.assertEqual(self.client.get(path+'?day='+day,headers=headers).json()['flagged_members'],[])
        body['stage']='preliminary'
        self.assertEqual(self.client.post(path+'/import',json=body,headers=headers).status_code,409)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).coin,Decimal(0))
            self.assertEqual(s.scalar(m.select(m.func.count()).select_from(reports.ReportBatch)),2)

    def test_reject_summary_and_foreign_game_user(self):
        with self.assertRaises(m.HTTPException):reports.parse_report('frequency,devices,revenue\n1,10,3\n')
        rows=reports.parse_report(HEADER+'999,p,28,10,0,CNY,1,a\n')
        self.assertFalse(reports.evaluate(rows,{1},reports.RuleInput(),'rechecked')[0]['flagged'])
        rows=reports.parse_report(HEADER+'1,p,28,10,0,USD,10,a\n')
        self.assertEqual(reports.evaluate(rows,{1},reports.RuleInput(),'rechecked')[0]['status'],'missing_estimate')

    def test_backend_basis_uses_shown_once_and_rejects_missing_prices(self):
        day=reports.datetime.now(reports.CN).date()-timedelta(days=3)
        with self.factory() as s:
            s.add(m.AppAdSession(id='report-ad',member_id=1,agent_id=1,game_id=1,request_id='report-request',provider='taku',
                ad_unit_id='p',impressed_at=reports.datetime.combine(day,reports.datetime.min.time(),reports.CN)+timedelta(hours=12),
                session_token_hash='unused',expires_at=m.now()))
            for stage in ['shown','reward','closed']:
                s.add(m.AppAdEvent(event_id='metadata:report-ad:'+stage,ad_session_id='report-ad',member_id=1,event_type='client_metadata',
                    result_json=json.dumps({'revenue_diagnostic':{'status':'decrypted','prices':[{'currency':'CNY','ecpm':'100'}]}})))
            s.commit()
        headers=self.admin_headers();path='/api/v1/games/1/taku-reports'
        self.client.put(path+'/rule',headers=headers,json={'min_impressions':1})
        self.client.post(path+'/import',headers=headers,json={'day':str(day),'stage':'rechecked','csv_text':HEADER+'1,p,28,1,0.07,CNY,0.09,a\n'})
        data=self.client.get(path+'?day='+str(day),headers=headers).json()
        self.assertEqual(data['flagged_members'],[1])
        self.assertEqual(data['items'][0]['backend_impressions'],1)
        self.assertEqual(Decimal(data['items'][0]['backend_estimate']),Decimal('.1'))
        self.client.post(path+'/import',headers=headers,json={'day':str(day),'stage':'rechecked','csv_text':HEADER+'1,p,28,2,0.07,CNY,0.09,a\n'})
        self.assertEqual(self.client.get(path+'?day='+str(day),headers=headers).json()['flagged_members'],[])

    def test_sync_607_keeps_existing_data_and_rejects_untrusted_download(self):
        with self.factory() as s:
            s.get(m.Game,1).settings_json=json.dumps({'ad_config':{'app_id':'test-app'}})
            s.add(m.TakuGlobalConfig(id=1,publisher_key='test-key',server_ecpm_key='{}',client_ecpm_key='{}'));s.commit()
        headers=self.admin_headers();path='/api/v1/games/1/taku-reports';day=str(reports.datetime.now(reports.CN).date()-timedelta(days=3))
        self.client.post(path+'/import',headers=headers,json={'day':day,'csv_text':HEADER+'1,p,28,3,0,CNY,1,a\n'})
        original=self.client.get(path+'?day='+day,headers=headers).json()['batch_id']
        with patch.object(sync,'read_url',side_effect=urllib.error.HTTPError('https://example',607,'no data',{},None)):
            result=self.client.post(path+'/sync?day='+day,headers=headers)
            self.assertEqual(result.json()['status'],'waiting_report')
        self.assertEqual(self.client.get(path+'?day='+day,headers=headers).json()['batch_id'],original)
        with patch.object(sync,'read_url',return_value='{"data":"https://127.0.0.1/secrets"}'):
            self.assertEqual(self.client.post(path+'/sync?day='+day,headers=headers).status_code,502)
        with patch.object(sync,'read_url',side_effect=[
            '{"data":["https://topon-openapi.s3.amazonaws.com/a","https://topon-openapi.s3.amazonaws.com/b"]}',
            HEADER+'1,p,28,3,0.1,CNY,1,a\n',HEADER+'1,p,28,3,0.2,CNY,1,a\n']):
            response=self.client.post(path+'/sync?day='+day,headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['status'],'imported')
        current=self.client.get(path+'?day='+day,headers=headers).json()
        self.assertEqual(current['items'][0]['impressions'],6)
        self.assertEqual(Decimal(current['items'][0]['revenue']),Decimal('0.3'))


if __name__ == '__main__': unittest.main()
