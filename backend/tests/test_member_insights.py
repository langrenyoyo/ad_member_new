"""Insights use independent temporary databases, never production services."""
from datetime import timedelta
from types import SimpleNamespace
from decimal import Decimal
import json
from sqlalchemy import select
import test_member_policy as fixtures
from app import main_from_txt as m
from app import member_insights as insights
import unittest


class InsightTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def test_review_labels_snapshot_and_fixed_reward(self):
        p=m.member_policy
        fixtures.MemberPolicyTests.policy(self,reward_enabled=True,label_rewards_enabled=True,
            label_window=4,label_min_samples=4,label_threshold='0.5',label_rewards={'finance':'10'},
            coins_per_yuan=100,whitelist_multiplier=3,max_reward=100)
        with self.factory() as s:
            for i in range(4):
                s.add(m.AppAdSession(id=f'review-{i}',member_id=1,agent_id=1,game_id=1,request_id=f'req-{i}',
                    impressed_at=m.now()+timedelta(seconds=i),session_token_hash='unused',expires_at=m.now()))
            s.commit()
        headers=self.admin_headers()
        def review(i,category='finance',revision=0):
            return self.client.put(f'/api/v1/ad-sessions/review-{i}/category-review',headers=headers,
                json={'category':category,'reason':'checked material','expected_revision':revision})
        self.assertEqual(review(0).status_code,200)
        self.assertEqual(review(0).status_code,409)
        self.assertEqual(review(1).status_code,200)
        with self.factory() as s:
            summary=insights.label_summary(s,1,p.policy(s,1))
            self.assertEqual(summary['label'],'unknown')  # exactly 50% is insufficient
            self.assertEqual(summary['counts']['unknown'],2)
        self.assertEqual(review(2).status_code,200)
        with self.factory() as s:
            user=s.get(m.Member,1);user.is_white=1
            captured=p.settlement_snapshot(s,user,1)
            self.assertEqual(captured['label_summary']['label'],'finance')
            s.add(m.AppAdEvent(event_id='policy:label-ad',ad_session_id='label-ad',member_id=1,
                event_type='policy_snapshot',result_json=json.dumps(captured)))
            s.commit()
        self.assertEqual(review(2,'unknown',1).status_code,200)
        with self.factory() as s:
            user=s.get(m.Member,1)
            self.assertEqual(p.settlement_snapshot(s,user,1)['label_summary']['label'],'unknown')
            proof={'prices':[{'currency':'CNY','ecpm':'40'}]}
            self.assertEqual(p.settle(s,user,SimpleNamespace(id='label-ad',game_id=1),'',proof,0),10)
            s.flush()
            ledger=s.scalar(select(p.RewardLedger).where(p.RewardLedger.ad_session_id=='label-ad'))
            self.assertEqual(ledger.amount,Decimal('10'))
            self.assertEqual(json.loads(ledger.rule_json)['reward_mode'],'label_fixed')
            s.commit()
        self.assertEqual(self.client.put('/api/v1/ad-sessions/review-3/category-review',headers=self.auth,
            json={'category':'finance','reason':'spoof','expected_revision':0}).status_code,401)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).coin,0) # reviews and standalone calculator never credit wallet
            self.assertEqual(s.scalar(select(m.func.count()).select_from(m.AppAdEvent).where(m.AppAdEvent.event_type=='category_review')),4)

    def test_fixed_reward_cap_and_policy_validation(self):
        p=m.member_policy
        rule=p.Policy(reward_enabled=True,label_rewards_enabled=True,label_rewards={'finance':'20'},max_reward=12)
        user=SimpleNamespace(is_white=True,ad_label='finance')
        self.assertEqual(p.calculate_reward(rule,user,'',{'prices':[{'currency':'CNY','ecpm':'40'}]})[0],12)
        for values in ({'label_rewards_enabled':True},{'label_window':2,'label_min_samples':3},
                       {'label_rewards':{'finance':'-1'}},{'label_rewards':{'finance':'1.0000001'}},
                       {'label_threshold':'0.49'}):
            with self.assertRaises(ValueError):p.Policy(**values)

    def test_metadata_is_owned_idempotent_and_non_settling(self):
        with self.factory() as s:
            s.add(m.AppAdSession(id='meta-ad',member_id=1,agent_id=1,game_id=1,request_id='meta-request',
                session_token_hash=m._token_hash('secret'),expires_at=m.now()+timedelta(minutes=5)))
            s.commit()
        path='/api/app/v1/ads/meta-ad/metadata'
        body={'session_token':'secret','event':'shown','network':'test','app_name':'sample','extension_keys':['app_name']}
        self.assertNotEqual(self.client.post(path,headers=self.other,json=body).status_code,200)
        self.assertNotEqual(self.client.post(path,headers=self.auth,json={**body,'session_token':'wrong'}).status_code,200)
        self.assertTrue(self.client.post(path,headers=self.auth,json=body).json()['data']['recorded'])
        self.assertFalse(self.client.post(path,headers=self.auth,json=body).json()['data']['recorded'])
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,1).coin,0)
            self.assertEqual(s.get(m.AppAdSession,'meta-ad').status,'issued')
        data=self.client.get('/api/v1/members/1/ad-settlements',headers=self.admin_headers()).json()
        self.assertEqual(data['items'][0]['client_metadata'][0]['app_name'],'sample')
        self.assertNotIn('session_token',data['items'][0]['client_metadata'][0])

    def test_encrypted_metadata_records_revenue_without_credit(self):
        import base64
        from unittest.mock import patch
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        cipher = base64.b64encode(key.public_key().encrypt(b'123_50_request1', padding.PKCS1v15())).decode()
        with self.factory() as s:
            s.add(m.AppAdSession(id='price-ad',member_id=1,agent_id=1,game_id=1,request_id='price-request',
                session_token_hash=m._token_hash('secret'),expires_at=m.now()+timedelta(minutes=5)))
            s.commit()
        body={'session_token':'secret','event':'shown','source_id':'123','s_id':'key1','e_c_cny':cipher}
        with patch('app.taku_ecpm._game_keys', return_value={'keys':{'key1':pem}}):
            self.assertEqual(self.client.post('/api/app/v1/ads/price-ad/metadata',headers=self.auth,json=body).status_code,200)
            self.assertEqual(self.client.post('/api/app/v1/ads/price-ad/metadata',headers=self.auth,
                json={**body,'event':'reward','source_id':'456'}).status_code,200)
        with self.factory() as s:
            rows=s.scalars(select(m.AppAdEvent).where(m.AppAdEvent.ad_session_id=='price-ad').order_by(m.AppAdEvent.id)).all()
            data=json.loads(rows[0].result_json)
            self.assertNotIn('e_c_cny',data)
            self.assertEqual(data['revenue_diagnostic']['prices'][0]['estimated_revenue'],'0.05')
            self.assertFalse(data['revenue_diagnostic']['settlement_eligible'])
            self.assertEqual(json.loads(rows[1].result_json)['revenue_diagnostic']['status'],'invalid_proof')
            self.assertEqual(s.get(m.Member,1).coin,0)
            self.assertIsNone(s.get(m.AppAdSession,'price-ad').coin_log_id)

    def test_late_impression_and_review_after_provider_reward(self):
        with self.factory() as s:
            s.add(m.AppAdSession(id='late-ad', member_id=1, agent_id=1, game_id=1,
                request_id='late-request', session_token_hash=m._token_hash('late-secret-value-123456789'),
                expires_at=m.now()+timedelta(minutes=5), status='rewarded', completed_at=m.now()))
            s.commit()
        body={'session_token':'late-secret-value-123456789','event_id':'late-impression'}
        self.assertEqual(self.client.post('/api/app/v1/ads/late-ad/impression',headers=self.auth,json=body).status_code,202)
        response=self.client.put('/api/v1/ad-sessions/late-ad/category-review',headers=self.admin_headers(),
            json={'category':'finance','reason':'reviewed provider creative','expected_revision':0})
        self.assertEqual(response.status_code,200,response.text)

    def test_movement_and_gaps_are_not_stationary(self):
        now=m.now()
        points=[SimpleNamespace(latitude=30+i*.0005,longitude=120,accuracy=5,device_id=1,
            created_at=now+timedelta(minutes=i)) for i in range(7)]
        self.assertEqual(insights.stable_duration(points),0)
        for p in points:p.latitude=30
        self.assertEqual(insights.stable_duration(points),360)
        points[3].latitude=None
        self.assertEqual(insights.stable_duration(points),0)

    def test_delete_bypasses_business_gate_but_not_auth(self):
        fixtures.MemberPolicyTests.policy(self,require_usage=True,block_signals=['root'])
        with self.factory() as s:
            s.add(insights.Observation(member_id=1,game_id=1,ip='test',battery=80,charging=1,created_at=m.now()))
            token=m._create_app_access_token(s.get(m.Member,1),recovery=True)
            s.commit()
        path='/api/app/v1/device-observations'
        self.assertEqual(self.client.delete(path).status_code,401)
        headers={'Authorization':'Bearer '+token,'X-Device-Risk':'root'}
        self.assertEqual(self.client.delete(path,headers=headers).status_code,200)
        self.assertEqual(self.client.post(path,headers=headers,json={'battery':80,'charging':True}).status_code,403)
        with self.factory() as s:self.assertEqual(len(s.scalars(select(insights.Observation)).all()),0)

    def test_retention_does_not_depend_on_new_samples(self):
        with self.factory() as s:
            for hours in (1,25):
                s.add(insights.Observation(member_id=1,game_id=1,ip='test',battery=80,charging=1,created_at=m.now()-timedelta(hours=hours)))
            s.commit()
        insights.purge_expired()
        with self.factory() as s:self.assertEqual(len(s.scalars(select(insights.Observation)).all()),1)

    def test_device_association_survives_challenge_expiry_and_is_install_bound(self):
        with self.factory() as s:
            s.add(m.device_risk.DeviceCheck(id='expired-verified',member_id=1,game_id=1,
                install_hash=m._token_hash('install-a'),device_id=10,status='consumed',
                verified_at=m.now()-timedelta(minutes=10),expires_at=m.now()-timedelta(minutes=5)))
            s.commit()
        body={'battery':80,'charging':True}
        self.client.post('/api/app/v1/device-observations',headers={**self.auth,'X-Device-Id':'install-a'},json=body)
        with self.factory() as s:self.assertEqual(s.scalar(select(insights.Observation)).device_id,10)
        self.client.delete('/api/app/v1/device-observations',headers=self.auth)
        self.client.post('/api/app/v1/device-observations',headers={**self.auth,'X-Device-Id':'different-install'},json=body)
        with self.factory() as s:self.assertIsNone(s.scalar(select(insights.Observation)).device_id)

    def test_observation_validation_rate_limit_and_delete(self):
        headers=self.admin_headers()
        body={'battery':80,'charging':True}
        self.assertEqual(self.client.post('/api/app/v1/device-observations',json=body).status_code,401)
        self.assertEqual(self.client.post('/api/app/v1/device-observations',headers=self.auth,json={**body,'latitude':1}).status_code,422)
        r=self.client.post('/api/app/v1/device-observations',headers=self.auth,json=body)
        self.assertTrue(r.json()['data']['recorded'])
        self.assertFalse(self.client.post('/api/app/v1/device-observations',headers=self.auth,json=body).json()['data']['recorded'])
        board=self.client.get('/api/v1/games/1/observation-board',headers=headers).json()
        self.assertEqual(board['total'],1)
        row=board['items'][0]
        self.assertIsNone(row['same_device_accounts'])
        self.assertIsNone(row['charging_ratio'])
        self.assertIsNone(row['nearby_verified_devices'])
        self.assertEqual(self.client.get('/api/v1/games/1/observation-board',headers=self.auth).status_code,401)
        self.client.delete('/api/app/v1/device-observations',headers=self.other)
        with self.factory() as s:self.assertEqual(len(s.scalars(select(insights.Observation)).all()),1)
        self.client.delete('/api/app/v1/device-observations',headers=self.auth)
        with self.factory() as s:self.assertEqual(len(s.scalars(select(insights.Observation)).all()),0)

    def test_board_counts_devices_not_accounts_and_ignores_stale_samples(self):
        headers=self.admin_headers()
        with self.factory() as s:
            for uid,device,lat in [(1,10,30),(2,10,30),(3,11,30.0001)]:
                s.add(insights.Observation(member_id=uid,game_id=1,device_id=device,ip='test',battery=80,
                    charging=1,latitude=lat,longitude=120,accuracy=5,created_at=m.now()))
            s.add(insights.Observation(member_id=4,game_id=1,device_id=12,ip='test',battery=80,
                charging=1,latitude=30,longitude=120,accuracy=5,created_at=m.now()-timedelta(minutes=11)))
            s.commit()
        board=self.client.get('/api/v1/games/1/observation-board?limit=1',headers=headers).json()
        self.assertEqual(board['total'],3)
        self.assertEqual(board['items'][0]['same_ip_verified_devices'],2)
        self.assertEqual(board['items'][0]['nearby_verified_devices'],1)

    def test_stationary_and_charge_need_continuous_observation(self):
        headers=self.admin_headers()
        observed_at=m.now()
        with self.factory() as s:
            for minute in range(6):
                s.add(insights.Observation(member_id=1,game_id=1,device_id=10,ip='test',battery=80,
                    charging=1,latitude=30,longitude=120,accuracy=5,created_at=observed_at-timedelta(minutes=minute)))
            s.commit()
        row=self.client.get('/api/v1/games/1/observation-board',headers=headers).json()['items'][0]
        self.assertEqual(row['charging_ratio'],1)
        self.assertEqual(row['location_stable_seconds'],300)

    def test_member_insights_separates_paid_withdrawals_and_categories(self):
        headers=self.admin_headers()
        r=self.client.get('/api/v1/members/1/insights',headers=headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['paid_withdrawal_cents'],0)
        self.assertEqual(r.json()['category_status'],'unknown')
        self.assertTrue(r.json()['commission_in_wallet'])
        self.assertEqual(self.client.get('/api/v1/members/999/insights',headers=headers).status_code,404)
        self.assertEqual(self.client.get('/api/v1/members/1/insights',headers=self.auth).status_code,401)
        self.assertEqual(self.client.get('/api/v1/members/1/ad-settlements',headers=headers).json(),{'total':0,'items':[]})
