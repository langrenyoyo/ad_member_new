import json
import sys
import tempfile
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import main_from_txt as m
from app import member_policy as p, sms_auth as sms


class MemberPolicyTests(unittest.TestCase):
    def test_all_upstream_agents_paid_with_snapshot(self):
        self.policy(commission_enabled=True,commission_rates=[0,0,0,'0.1'])
        with self.factory() as s:
            user=s.get(m.Member,1);p.enrollment(s,user).parent_id=2
            s.get(p.Enrollment,2).level=3
            agent=m.Member(id=3,username='upper',game_id=1,agent_id=1,status=1,coin=0)
            s.add(agent);s.flush();p.enrollment(s,agent).level=3
            s.get(p.Enrollment,2).parent_id=3;s.flush()
            captured=p.settlement_snapshot(s,user,1)
            self.assertEqual(captured['recipients'][3],[2,3])
            s.add(m.AppAdEvent(event_id='policy:multi-agent',ad_session_id='multi-agent',member_id=1,
                event_type='policy_snapshot',result_json=json.dumps(captured)));s.flush()
            s.get(p.Enrollment,2).parent_id=0
            p.settle(s,user,SimpleNamespace(id='multi-agent',game_id=1),'',None,100)
            s.flush()
            self.assertEqual(s.get(m.Member,2).coin,10)
            self.assertEqual(s.get(m.Member,3).coin,10)

    def test_registration_parent_identity_and_atomic_binding(self):
        with self.factory() as s:
            user=s.get(m.Member,1);parent=s.get(p.Enrollment,2)
            for level in (0,2):
                parent.level=level;s.flush()
                with self.assertRaises(m.HTTPException):p.bind_registration(s,user,parent.invite_code)
                self.assertFalse(user.parent_id)
            for level in (1,3):
                parent.level=level;s.flush();p.bind_registration(s,user,parent.invite_code.lower())
                self.assertEqual(user.parent_id,2)
                self.assertEqual(s.get(p.Enrollment,1).parent_id,2)

    def test_agent_receives_indirect_descendants_and_white_retry(self):
        with self.factory() as s:
            user=s.get(m.Member,1);p.enrollment(s,user).parent_id=2
            agent=m.Member(id=3,username='upstream-agent',game_id=1,agent_id=1,status=1)
            s.add(agent);s.flush();p.enrollment(s,agent).level=3
            s.get(p.Enrollment,2).parent_id=3;s.flush()
            self.assertEqual(p.commission_recipients(s,user,p.Policy()),{1:2,3:3})
            s.add(m.device_risk.DeviceRule(game_id=1,enabled=1));user.is_white=1;s.flush()
            m.device_risk.authorize_retry(s,SimpleNamespace(game_id=1,risk_check_id=None),SimpleNamespace(id='white',member_id=1))

    def test_whitelist_range_precedes_disabled_policy_and_cap(self):
        self.policy(reward_enabled=False,commission_enabled=False,max_reward=1)
        with self.factory() as s:
            user=s.get(m.Member,1);user.is_white=1
            user.whitelist_min_coin=Decimal('5');user.whitelist_max_coin=Decimal('5')
            captured=p.settlement_snapshot(s,user,1)
            s.add(m.AppAdEvent(event_id='policy:white-priority',ad_session_id='white-priority',member_id=1,
                event_type='policy_snapshot',result_json=json.dumps(captured)));s.flush()
            user.whitelist_min_coin=99;user.whitelist_max_coin=100
            amount=p.settle(s,user,SimpleNamespace(id='white-priority',game_id=1),'',None,1)
            self.assertEqual(amount,5)
            s.flush()
            ledger=s.scalar(select(p.RewardLedger).where(p.RewardLedger.ad_session_id=='white-priority'))
            self.assertEqual(ledger.amount,5)

    def test_whitelist_partial_update_validates_merged_range(self):
        headers=self.admin_headers();path='/api/v1/members/1'
        self.assertEqual(self.client.patch(path,headers=headers,json={'whitelist_min_coin':'5','whitelist_max_coin':'10'}).status_code,200)
        for body in ({'whitelist_min_coin':'11'},{'whitelist_max_coin':None},{'whitelist_min_coin':'1.0000001'}):
            self.assertEqual(self.client.patch(path,headers=headers,json=body).status_code,422)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).whitelist_min_coin,5)
            self.assertEqual(s.get(m.Member,1).whitelist_max_coin,10)
        self.assertEqual(self.client.patch(path,headers=headers,json={'whitelist_min_coin':None,'whitelist_max_coin':None}).status_code,200)

    def test_announcement_change_does_not_revalidate_unchanged_settlement(self):
        import os
        self.policy(reward_enabled=True,reward_basis='verified_cny_ecpm')
        headers=self.admin_headers()
        body=p.Policy(reward_enabled=True).model_dump(mode='json')
        with patch.dict(os.environ,TAKU_ECPM_KEYRING_FILE=str(Path(self.temp.name)/'missing.json')):
            body['announcement']='maintenance'
            self.assertEqual(self.client.put('/api/v1/games/1/member-policy',headers=headers,json=body).status_code,200)
            body['max_reward']='99'
            self.assertEqual(self.client.put('/api/v1/games/1/member-policy',headers=headers,json=body).status_code,503)
            with self.assertRaises(m.HTTPException):p.check_reward_configuration(1,p.Policy(reward_enabled=True))
    def test_keyring_failure_allows_management_but_not_verified_rewards(self):
        import os
        headers=self.admin_headers()
        with patch.dict(os.environ,TAKU_ECPM_KEYRING_FILE=str(Path(self.temp.name)/'missing.json')):
            response=self.client.put('/api/v1/games/1/member-policy',headers=headers,
                json={'reward_enabled':False,'announcement':'maintenance'})
            self.assertEqual(response.status_code,200,response.text)
            response=self.client.put('/api/v1/games/1/member-policy',headers=headers,
                json={'reward_enabled':True,'reward_basis':'verified_cny_ecpm'})
            self.assertEqual(response.status_code,503)
            with self.assertRaises(m.HTTPException):p.check_reward_configuration(1,p.Policy())
    def test_ecpm_tier_boundaries_and_override(self):
        rule=p.Policy(reward_enabled=True,tier_enabled=True,coins_per_yuan=100,max_reward=100000,
            ecpm_tiers=[{'upper':50,'percent':200},{'upper':100,'percent':70}])
        for ecpm,rate in [('0','2'),('50','2'),('50.000001','.7'),('100','.7'),('4000','.7')]:
            amount,detail=p.calculate_reward(rule,SimpleNamespace(is_white=0),'',{'prices':[{'currency':'CNY','ecpm':ecpm}]})
            self.assertEqual(amount,(Decimal(ecpm)/1000*100*Decimal(rate)).quantize(Decimal('.000001'),rounding=p.ROUND_DOWN))
            self.assertEqual(Decimal(detail['release_rate']),Decimal(rate))
        with self.assertRaises(ValueError):p.Policy(tier_enabled=True)
        with self.assertRaises(ValueError):p.Policy(tier_enabled=True,reward_basis='fixed_ecpm',ecpm_tiers=[{'upper':50,'percent':200}])
        with self.assertRaises(ValueError):p.Policy(ecpm_tiers=[{'upper':50,'percent':200},{'upper':50,'percent':70}])
        with self.assertRaises(ValueError):p.Policy(ecpm_tiers=[{'upper':50,'percent':1001}])

    def test_tier_snapshot_and_preview_no_balance_mutation(self):
        values=dict(reward_enabled=True,tier_enabled=True,coins_per_yuan=100,max_reward=1000,
            ecpm_tiers=[{'upper':50,'percent':200},{'upper':100,'percent':70}])
        self.policy(**values)
        with self.factory() as s:
            user=s.get(m.Member,1)
            s.add(m.AppAdEvent(event_id='policy:tier',ad_session_id='tier',member_id=1,event_type='policy_snapshot',result_json=json.dumps(p.settlement_snapshot(s,user,1))))
            s.get(m.Game,1).settings_json='{}';s.flush()
            self.assertEqual(p.settle(s,user,SimpleNamespace(id='tier',game_id=1),'',{'prices':[{'currency':'CNY','ecpm':'40'}]},0),8)
            s.commit()
        response=self.client.post('/api/v1/member-policy/reward-preview',headers=self.admin_headers(),json={'policy':values,'ecpm':'40'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(Decimal(response.json()['coin']),8)
        with self.factory() as s:self.assertEqual(s.get(m.Member,1).coin,0)
    def admin_headers(self):
        with self.factory() as s:
            admin=m.AdminUser(username='boundary-admin',password_hash='unused',password_salt='unused',role='superadmin',status=1)
            s.add(admin);s.commit()
            return {'Authorization':'Bearer '+m.create_access_token(admin)}

    def test_opening_balance_and_invite_must_use_business_endpoints(self):
        headers=self.admin_headers()
        for key in ('coin','freeze_coin','coin_user','coin_user_month','coin_user_day','parent_id'):
            for value in (100,-1):
                result=self.client.post('/api/v1/members',headers=headers,json={
                    'username':'invalid-opening','agent_id':1,'game_id':1,key:value})
                self.assertEqual(result.status_code,422,result.text)
        result=self.client.post('/api/v1/members',headers=headers,json={
            'username':'zero-opening','agent_id':1,'game_id':1,'coin':0,'parent_id':0})
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(result.json()['coin'],0)
        self.assertEqual(self.client.delete('/api/v1/members/'+str(result.json()['id']),headers=headers).status_code,204)

    def test_adjustment_precision_boundary(self):
        headers=self.admin_headers()
        body={'coin':'999999999999999999.123456','freeze_coin':0,'expected_coin':0,'expected_freeze_coin':0,'reason':'precision'}
        path='/api/v1/members/1/adjust-balance'
        self.assertEqual(self.client.post(path,headers=headers,json=body).status_code,422)
        body['coin']='999999999.123456'
        self.assertEqual(self.client.post(path,headers=headers,json=body).status_code,200)
        with self.factory() as s:
            self.assertEqual(Decimal(str(s.get(m.Member,1).coin)),Decimal(body['coin']))
            log=s.scalar(select(m.CoinLog))
            self.assertEqual(Decimal(str(log.coin)),Decimal(body['coin']))
        body.update(expected_coin=body['coin'],coin='1.1234567')
        self.assertEqual(self.client.post(path,headers=headers,json=body).status_code,422)

    def test_delete_protects_alipay_refresh_and_balance(self):
        headers=self.admin_headers()
        with self.factory() as s:
            for uid in (3,4,5):s.add(m.Member(id=uid,username='protected-'+str(uid),game_id=1,agent_id=1,status=1))
            s.flush()
            s.add(m.payouts.AlipayAccount(member_id=3,account='test',real_name='test'))
            m._new_refresh_session(s,s.get(m.Member,4),'device')
            s.get(m.Member,5).coin=1
            s.commit()
        for uid in (3,4,5):
            self.assertEqual(self.client.delete('/api/v1/members/'+str(uid),headers=headers).status_code,409)
        with self.factory() as s:
            self.assertIsNotNone(s.get(m.payouts.AlipayAccount,3))
            self.assertTrue(all(s.get(m.Member,uid) is not None for uid in (3,4,5)))

    def test_production_seed_disables_legacy_and_has_no_demo_data(self):
        with self.factory() as s:
            hashed,salt=m.hash_password('123456')
            s.add(m.AdminUser(username='18532306918',password_hash=hashed,password_salt=salt,role='superadmin',status=1))
            s.commit()
        with patch.object(m,'engine',self.engine), patch.object(m,'APP_ENV','production'):
            m.seed_data()
        with self.factory() as s:
            self.assertEqual(s.scalar(select(m.AdminUser).where(m.AdminUser.username=='18532306918')).status,0)
            self.assertIsNone(s.get(m.Agent,133))
            self.assertIsNotNone(s.scalar(select(m.AdminUser).where(m.AdminUser.username==m.ADMIN_USERNAME)))

    def test_member_edit_cannot_bypass_accounting_or_invites(self):
        with self.factory() as s:
            admin=m.AdminUser(username='audit',password_hash='unused',password_salt='unused',role='superadmin',status=1)
            s.add(admin)
            user=s.get(m.Member,1);user.parent_id=2;p.enrollment(s,user).parent_id=2
            s.commit();headers={'Authorization':'Bearer '+m.create_access_token(admin)}
        for body in ({'coin':100},{'freeze_coin':10},{'parent_id':0},{'game_id':2}):
            self.assertEqual(self.client.patch('/api/v1/members/1',headers=headers,json=body).status_code,409)
        self.assertEqual(self.client.patch('/api/v1/members/1',headers=headers,json={'name':'safe','coin':0,'parent_id':2}).status_code,200)
        self.assertEqual(self.client.delete('/api/v1/members/2',headers=headers).status_code,409)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).parent_id,s.get(p.Enrollment,1).parent_id)
            self.assertEqual(s.get(m.Member,1).coin,0)
        adjustment={'coin':'12.123456','freeze_coin':'0','expected_coin':'0','expected_freeze_coin':'0','reason':'audit test'}
        path='/api/v1/members/1/adjust-balance'
        self.assertEqual(self.client.post(path,headers=headers,json=adjustment).status_code,200)
        self.assertEqual(self.client.post(path,headers=headers,json=adjustment).status_code,409)
        self.assertEqual(self.client.post(path,headers=self.auth,json=adjustment).status_code,401)
        with self.factory() as s:
            self.assertEqual(len(s.scalars(select(m.CoinLog)).all()),1)
        rebind={'parent_id':0,'expected_parent_id':2,'ht_id':0,'ht_top_id':0}
        self.assertEqual(self.client.post('/api/v1/members/1/rebind',headers=headers,json=rebind).status_code,200)
        self.assertEqual(self.client.post('/api/v1/members/1/rebind',headers=headers,json=rebind).status_code,409)
        rebind.update(parent_id=1,expected_parent_id=0)
        self.assertEqual(self.client.post('/api/v1/members/1/rebind',headers=headers,json=rebind).status_code,422)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).parent_id,0)
            self.assertEqual(s.get(p.Enrollment,1).parent_id,0)

    def test_clear_coins_preserves_frozen_withdrawals_and_audits(self):
        with self.factory() as s:
            admin=m.AdminUser(username='audit',password_hash='unused',password_salt='unused',role='superadmin',status=1)
            s.add(admin);s.get(m.Member,1).coin=10;s.get(m.Member,1).freeze_coin=2
            s.commit();headers={'Authorization':'Bearer '+m.create_access_token(admin)}
        path='/api/v1/members/1/clear-coins'
        self.assertEqual(self.client.post(path,headers=headers,json={'reason':'test'}).status_code,409)
        with self.factory() as s:s.get(m.Member,1).freeze_coin=0;s.commit()
        self.assertEqual(self.client.post(path,headers=headers,json={'reason':'test'}).status_code,200)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).coin,0)
            self.assertEqual(s.scalar(select(m.CoinLog)).coin,-10)
            self.assertIsNotNone(s.scalar(select(m.AdminOperation)))

    def test_cooldown_refresh_is_recovery_only(self):
        self.policy(reset_login_block=True)
        with self.factory() as s:
            member=s.get(m.Member,1)
            refresh=m._new_refresh_session(s,member,'device')
            d=m.device_risk.RiskDevice(game_id=1,device_key='recovery',override='restrict')
            s.add(d);s.flush()
            s.add(m.device_risk.DeviceCheck(id='recovery-check',member_id=1,game_id=1,install_hash='hash',device_id=d.id,
                expires_at=m.now()+timedelta(minutes=5)))
            p.admit_rolling(s,d,member,1)
            s.commit()
        response=self.client.post('/api/app/v1/auth/refresh',json={'refresh_token':refresh,'device_id':'device'})
        self.assertEqual(response.status_code,200,response.text)
        headers={'Authorization':'Bearer '+response.json()['data']['access_token']}
        self.assertEqual(self.client.get('/api/app/v1/me',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/app/v1/wallet',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/app/v1/onboarding',headers=headers).status_code,403)
        self.assertEqual(self.client.get('/api/app/v1/bootstrap',headers=headers).status_code,403)
        self.assertEqual(self.client.patch('/api/app/v1/me',headers=headers,json={'name':'changed'}).status_code,403)
        self.assertEqual(self.client.post('/api/app/v1/withdrawals',headers=headers,json={
            'request_key':'new-withdrawal','game_id':1,'amount_cents':500}).status_code,403)

    def test_sms_password_bound_to_current_member_and_one_use(self):
        with self.factory() as s:
            s.get(m.Member,1).username='13800000000'
            s.get(m.Game,1).settings_json=json.dumps({'member_policy':{'require_alipay':True,'require_invite':True}})
            s.add(sms.SmsCode(id='set-pass',phone_hash=sms.digest('13800000000'),ip_hash='ip',game_id=1,
                code_hash=sms.digest('set-pass123456'),expires_at=m.now()+timedelta(minutes=5),state='ready'))
            s.commit()
        body={'challenge_id':'set-pass','code':'123456','new_password':'NewPassword123'}
        self.assertEqual(self.client.post('/api/app/v1/auth/sms/password',headers=self.other,json=body).status_code,401)
        response=self.client.post('/api/app/v1/auth/sms/password',headers=self.auth,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post('/api/app/v1/auth/sms/password',headers=self.auth,json=body).status_code,401)
        with self.factory() as s:
            member=s.get(m.Member,1)
            self.assertTrue(m.verify_password('NewPassword123',member.password_hash,member.password_salt))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///'+str(Path(self.temp.name)/'db.sqlite'), connect_args={'check_same_thread':False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patch = patch.object(m, 'SessionLocal', self.factory)
        self.patch.start()
        self.client = TestClient(m.app)
        with self.factory() as s:
            s.add_all([m.Agent(id=1,name='agent'),m.Game(id=1,name='game',agent_id=1),
                m.Member(id=1,username='wx_user',game_id=1,agent_id=1,coin=0,status=1),
                m.Member(id=2,username='parent',game_id=1,agent_id=1,coin=0,status=1)])
            s.flush()
            self.auth={'Authorization':'Bearer '+m._create_app_access_token(s.get(m.Member,1))}
            self.other={'Authorization':'Bearer '+m._create_app_access_token(s.get(m.Member,2))}
            p.enrollment(s,s.get(m.Member,2)).level=1
            s.commit()

    def tearDown(self):
        self.client.close();self.patch.stop();self.engine.dispose();self.temp.cleanup()

    def policy(self, **values):
        with self.factory() as s:
            s.get(m.Game,1).settings_json=json.dumps({'member_policy':values})
            s.commit()

    def test_invite_gate_qualification_and_cycle(self):
        self.policy(require_invite=True)
        self.assertEqual(self.client.get('/api/app/v1/wallet',headers=self.auth).status_code,403)
        a=self.client.get('/api/app/v1/onboarding',headers=self.auth)
        self.assertEqual(a.status_code,200,a.text)
        b=self.client.get('/api/app/v1/onboarding',headers=self.other).json()['data']
        result=self.client.post('/api/app/v1/onboarding',headers=self.auth,json={'invite_code':b['invite_code']})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/app/v1/wallet',headers=self.auth).status_code,200)
        with self.factory() as s:
            row=s.get(p.Enrollment,1);row.level=1;code=row.invite_code;s.commit()
        self.assertEqual(self.client.post('/api/app/v1/onboarding',headers=self.other,json={'invite_code':code}).status_code,422)

    def test_usage_upsert_and_revocation_gate(self):
        self.policy(require_usage=True)
        body={'granted':True,'report_date':(m.now()+timedelta(hours=8)).date().isoformat(),
            'items':[{'package_name':'com.example.app','duration_ms':1000,'opens':2}]}
        for _ in range(2):
            result=self.client.post('/api/app/v1/usage',headers=self.auth,json=body)
            self.assertEqual(result.status_code,200,result.text)
        with self.factory() as s:self.assertEqual(len(s.scalars(select(p.UsageReport)).all()),1)
        self.assertEqual(self.client.get('/api/app/v1/wallet',headers=self.auth).status_code,200)
        body['granted']=False
        self.client.post('/api/app/v1/usage',headers=self.auth,json=body)
        self.assertEqual(self.client.get('/api/app/v1/wallet',headers=self.auth).status_code,403)

    def test_reward_multiplier_commission_and_limits(self):
        self.policy(reward_enabled=True,reward_basis='fixed_ecpm',fixed_ecpm='100',coins_per_yuan='100',
            whitelist_multiplier='2',commission_rates=['0','.1','0','0'])
        with self.factory() as s:
            user=s.get(m.Member,1);user.is_white=1
            p.enrollment(s,user).parent_id=2
            reward=p.settle(s,user,SimpleNamespace(id='ad1',game_id=1),'1',None,0)
            self.assertEqual(reward,20)
            s.commit()
            self.assertEqual(s.get(m.Member,2).coin,2)
            self.assertEqual(len(s.scalars(select(p.RewardLedger)).all()),2)
        with self.assertRaises(ValueError):p.Policy(commission_rates=['.5','.5','.5','0'])

    def test_commission_independent_of_reward_and_summary(self):
        self.policy(commission_enabled=True, commission_rates=['0','.1','0','0'])
        with self.factory() as s:
            user=s.get(m.Member,1)
            p.enrollment(s,user).parent_id=2
            self.assertEqual(p.settle(s,user,SimpleNamespace(id='legacy',game_id=1),'1',None,20),20)
            s.commit()
            self.assertEqual(s.get(m.Member,2).coin,2)
        data=self.client.get('/api/app/v1/commissions?limit=1',headers=self.other).json()['data']
        self.assertEqual(data['total'],1)
        self.assertEqual(Decimal(data['summary']['today_earned']),2)
        self.assertEqual(Decimal(data['summary']['total_earned']),2)
        self.assertEqual(data['summary']['direct_members'],1)
        team=self.client.get('/api/app/v1/commission-team',headers=self.other).json()['data']
        self.assertEqual(team['total'],1)
        self.assertEqual(team['items'],[{'id':1,'level':0}])
        self.assertEqual((team['page'],team['page_size'],team['total_pages'],team['has_more']),
                         (1,20,1,False))
        self.assertEqual(self.client.get('/api/app/v1/commission-team',headers=self.auth).json()['data']['total'],0)
        self.assertEqual(self.client.get('/api/app/v1/commissions',headers=self.auth).json()['data']['total'],0)

    def test_snapshot_preserves_recipient_rate_and_whitelist(self):
        self.policy(reward_enabled=True,reward_basis='fixed_ecpm',fixed_ecpm='100',coins_per_yuan='100',
            whitelist_multiplier='2',commission_rates=['0','.1','0','0'])
        with self.factory() as s:
            user=s.get(m.Member,1); user.is_white=1
            row=p.enrollment(s,user); row.parent_id=2
            captured=p.settlement_snapshot(s,user,1)
            s.add(m.AppAdEvent(event_id='policy:snapshot',ad_session_id='snapshot',member_id=1,
                event_type='policy_snapshot',result_json=json.dumps(captured)))
            row.parent_id=0; user.is_white=0
            s.get(p.Enrollment,2).level=2
            s.get(m.Game,1).settings_json='{}'
            s.flush()
            self.assertEqual(p.settle(s,user,SimpleNamespace(id='snapshot',game_id=1),'1',None,0),20)
            s.commit()
            self.assertEqual(s.get(m.Member,2).coin,2)

    def test_whitelist_member_coin_range_is_randomized_once_in_snapshot(self):
        self.policy(reward_enabled=True, reward_basis='fixed_ecpm', fixed_ecpm='100', coins_per_yuan='100',
            whitelist_multiplier='2')
        with self.factory() as s:
            user=s.get(m.Member,1); user.is_white=1
            user.whitelist_min_coin=10; user.whitelist_max_coin=20
            with patch('app.member_policy.secrets.randbelow', return_value=3):
                captured=p.settlement_snapshot(s,user,1)
            self.assertEqual(captured['whitelist_range_reward'], '10.000003')
            s.add(m.AppAdEvent(event_id='policy:range',ad_session_id='range',member_id=1,
                event_type='policy_snapshot',result_json=json.dumps(captured)))
            self.assertEqual(p.settle(s,user,SimpleNamespace(id='range',game_id=1),'1',None,0), Decimal('10.000003'))
            s.commit()
            ledger=s.scalar(select(p.RewardLedger).where(p.RewardLedger.ad_session_id=='range'))
            self.assertEqual(json.loads(ledger.rule_json)['reward_mode'], 'whitelist_range')

    def test_agent_demotion_blocks_snapshotted_commission(self):
        self.policy(commission_enabled=True,agent_member_id=2,commission_rates=['0','0','0','.1'])
        with self.factory() as s:
            s.get(p.Enrollment,2).level=3
            user=s.get(m.Member,1)
            captured=p.settlement_snapshot(s,user,1)
            s.add(m.AppAdEvent(event_id='policy:demoted',ad_session_id='demoted',member_id=1,
                event_type='policy_snapshot',result_json=json.dumps(captured)))
            s.get(p.Enrollment,2).level=1; s.flush()
            p.settle(s,user,SimpleNamespace(id='demoted',game_id=1),'1',None,20)
            s.commit()
            self.assertEqual(s.get(m.Member,2).coin,0)
            ledger=s.scalar(select(p.RewardLedger).where(p.RewardLedger.ad_session_id=='demoted'))
            outcome=json.loads(ledger.rule_json)['commission_outcomes'][0]
            self.assertEqual((outcome['eligible'],outcome['reason']), (False,'等级不满足'))
            from app.wallet_audit import reconcile
            self.assertNotIn('expected_commission_missing', {f['kind'] for f in reconcile(s)['findings']})

    def test_explicit_commission_disable_preserves_custom_reward(self):
        self.policy(reward_enabled=True,commission_enabled=False,reward_basis='fixed_ecpm',
            fixed_ecpm='100',coins_per_yuan='100',commission_rates=['0','.1','0','0'])
        with self.factory() as s:
            user=s.get(m.Member,1); p.enrollment(s,user).parent_id=2
            self.assertEqual(p.settle(s,user,SimpleNamespace(id='off',game_id=1),'1',None,0),10)
            s.commit()
            self.assertEqual(s.get(m.Member,2).coin,0)

    def test_global_agent_paid_once_and_never_self(self):
        self.policy(commission_enabled=True,agent_member_id=2,commission_rates=['0','0','0','.1'])
        with self.factory() as s:
            s.get(p.Enrollment,2).level=3
            user=s.get(m.Member,1); p.enrollment(s,user).parent_id=2
            p.settle(s,user,SimpleNamespace(id='once',game_id=1),'1',None,20)
            agent=s.get(m.Member,2)
            p.settle(s,agent,SimpleNamespace(id='self',game_id=1),'1',None,20)
            s.commit()
            self.assertEqual(agent.coin,2)
            rows=s.scalars(select(p.RewardLedger).where(p.RewardLedger.kind=='commission_3')).all()
            self.assertEqual(len(rows),1)
            # Ledger uniqueness rolls back a duplicate together with its balance mutation.
            from sqlalchemy.exc import IntegrityError
            with self.assertRaises(IntegrityError):
                p.settle(s,user,SimpleNamespace(id='once',game_id=1),'1',None,20)
                s.commit()
            s.rollback()
            self.assertEqual(s.get(m.Member,2).coin,2)

    def test_admin_ledger_pagination_and_member_access(self):
        with self.factory() as s:
            admin=m.AdminUser(username='root',password_hash='unused',password_salt='unused',role='superadmin',status=1)
            s.add(admin)
            for index in range(3):
                s.add(p.RewardLedger(ad_session_id=str(index),member_id=1,beneficiary_id=2,
                    game_id=1,kind='commission_1',amount=Decimal('1'),rule_json='{}'))
            s.commit()
            headers={'Authorization':'Bearer '+m.create_access_token(admin)}
        page=self.client.get('/api/v1/games/1/reward-ledgers?limit=2&offset=2',headers=headers)
        self.assertEqual(page.status_code,200,page.text)
        self.assertEqual(page.json()['total'],3)
        self.assertEqual(len(page.json()['items']),1)
        self.assertEqual(self.client.get('/api/v1/games/1/reward-ledgers',headers=self.auth).status_code,401)

    def test_risk_block_expiry_and_shared_device(self):
        self.policy(reset_login_block=True)
        with self.factory() as s:
            d=m.device_risk.RiskDevice(game_id=1,device_key='shared',override='restrict')
            s.add(d);s.flush()
            s.add(m.device_risk.DeviceCheck(id='check',member_id=1,game_id=1,install_hash='hash',device_id=d.id,
                expires_at=m.now()+timedelta(minutes=5)))
            p.admit_rolling(s,d,s.get(m.Member,1),1)
            s.commit()
        self.assertEqual(self.client.get('/api/app/v1/onboarding',headers=self.auth).status_code,403)
        with self.factory() as s:
            s.query(p.DeviceCooldown).one().blocked_until=m.now()-timedelta(seconds=1)
            s.commit()
        self.assertEqual(self.client.get('/api/app/v1/me',headers=self.auth).status_code,200)

    def test_sms_single_use_wrong_attempts_and_throttle(self):
        captured=[]
        with patch.object(sms,'send_sms',side_effect=lambda phone,code:captured.append(code)):
            result=self.client.post('/api/app/v1/auth/sms/send',json={'phone':'13800000000','game_id':1})
            self.assertEqual(result.status_code,200,result.text)
            challenge=result.json()['data']['challenge_id']
            self.assertEqual(self.client.post('/api/app/v1/auth/sms/send',json={'phone':'13800000000','game_id':1}).status_code,429)
        body={'phone':'13800000000','game_id':1,'device_id':'device','challenge_id':challenge,'code':captured[0],'new_password':'Password123'}
        self.assertEqual(self.client.post('/api/app/v1/auth/sms/login',json=body).status_code,422)
        with self.factory() as s:
            self.assertIsNone(s.scalar(select(m.Member).where(m.Member.username=='13800000000')))
            body['invite_code']=s.get(p.Enrollment,2).invite_code
        result=self.client.post('/api/app/v1/auth/sms/login',json=body)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.post('/api/app/v1/auth/sms/login',json=body).status_code,401)

    def test_admin_policy_save_and_permission(self):
        with self.factory() as s:
            admin=m.AdminUser(username='root',password_hash='unused',password_salt='unused',role='superadmin',status=1)
            s.add(admin);s.commit()
            headers={'Authorization':'Bearer '+m.create_access_token(admin)}
        result=self.client.put('/api/v1/games/1/member-policy',headers=headers,json={'require_invite':True,'announcement':'notice'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/app/v1/policy?game_id=1').json()['data']['announcement'],'notice')
        self.assertEqual(self.client.put('/api/v1/games/1/member-policy',headers=self.auth,json={}).status_code,401)
        with self.factory() as s:self.assertEqual(len(s.scalars(select(m.AdminOperation)).all()),1)

    def test_sms_locked_after_five_wrong_codes(self):
        with patch.object(sms,'send_sms'):
            result=self.client.post('/api/app/v1/auth/sms/send',json={'phone':'13900000000','game_id':1})
        challenge=result.json()['data']['challenge_id']
        with self.factory() as s:
            s.get(sms.SmsCode,challenge).code_hash=sms.digest(challenge+'123456');s.commit()
        body={'phone':'13900000000','game_id':1,'device_id':'d','challenge_id':challenge,'code':'000000'}
        for _ in range(5):self.assertEqual(self.client.post('/api/app/v1/auth/sms/login',json=body).status_code,401)
        body['code']='123456'
        self.assertEqual(self.client.post('/api/app/v1/auth/sms/login',json=body).status_code,401)

    def test_whitelist_does_not_bypass_invitation(self):
        self.policy(require_invite=True,whitelist_risk_exempt=True,block_signals=['developer'])
        with self.factory() as s:s.get(m.Member,1).is_white=1;s.commit()
        result=self.client.get('/api/app/v1/wallet',headers={**self.auth,'X-Device-Risk':'developer'})
        self.assertEqual(result.status_code,403)
        self.assertEqual(result.json()['detail']['code'],'INVITE_REQUIRED')


if __name__=='__main__':unittest.main()
