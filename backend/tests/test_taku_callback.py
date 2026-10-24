"""TAKU callbacks exercise a temporary database; never contact the live provider."""
import hashlib
import base64
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app import main_from_txt as m
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding


class TakuCallbackTests(unittest.TestCase):
    def test_placeholder_proof_rejected_with_standard_status_and_audit(self):
        self.configure_ecpm()
        response=self.callback(self.params(e_c='{e_c}',e_c_cny='{e_c_cny}',s_id='{s_id}'))
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.headers['x-taku-result-code'],'602')
        self.assertEqual(self.balances(),(10,0,0))
        with self.factory() as s:
            row=s.scalar(select(m.AdFlowLog).where(m.AdFlowLog.error_code=='ecpm_placeholder'))
            self.assertIsNotNone(row)

    def test_global_keys_permissions_preservation_and_real_decryption(self):
        from app.taku_settings import global_ecpm_keys
        admin = m.AdminUser(id=99, username='key-admin', role='superadmin', status=1)
        self.client.app.dependency_overrides[m.require_admin] = lambda: admin
        try:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
            payload = {'publisher_key': 'global-publisher-secret', 'server_ecpm_key': pem,
                       'server_ecpm_key_id': 'server-1', 'client_ecpm_key': pem, 'client_ecpm_key_id': 'client-1'}
            response = self.client.patch('/api/v1/settings/taku-keys', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn(pem, response.text)
            self.assertNotIn('global-publisher-secret', response.text)
            self.assertEqual(self.client.patch('/api/v1/settings/taku-keys', json={}).json(), response.json())
            self.assertEqual(set(global_ecpm_keys()), {'server-1', 'client-1'})
            with self.factory() as s:
                self.assertEqual(m.taku_credentials(s, 1), (True, 'global-publisher-secret'))
                s.add(m.GameTakuConfig(game_id=1, enabled=1, sec_key='test-taku-key')); s.commit()
            cipher = base64.b64encode(key.public_key().encrypt(b'123_2.5_sdk-global', padding.PKCS1v15())).decode()
            self.assertEqual(self.callback(self.params(e_c_cny=cipher, s_id='client-1')).status_code, 200)
            bad = self.client.patch('/api/v1/settings/taku-keys', json={'server_ecpm_key':'bad-private', 'server_ecpm_key_id':'bad'})
            self.assertEqual(bad.status_code, 422)
            self.assertNotIn('bad-private', bad.text)
            admin.role = 'operator'
            self.assertEqual(self.client.get('/api/v1/settings/taku-keys').status_code, 403)
            self.assertEqual(self.client.patch('/api/v1/settings/taku-keys', json=payload).status_code, 403)
        finally:
            self.client.app.dependency_overrides.pop(m.require_admin, None)

    def test_entire_commission_loss_is_detected_from_settlement_outcome(self):
        from app.wallet_audit import reconcile
        from app import member_policy as p
        with self.factory() as s:
            s.get(m.Game,1).settings_json=json.dumps({'member_policy':{'reward_enabled':True,
                'reward_basis':'fixed_ecpm','fixed_ecpm':'1000','commission_rates':['0','.1','0','0']}})
            parent=m.Member(username='missing-commission-parent',game_id=1,agent_id=1,coin=0)
            s.add(parent);s.flush()
            parent_id=parent.id
            p.enrollment(s,parent).level=1
            p.enrollment(s,s.get(m.Member,self.uid)).parent_id=parent_id
            s.commit()
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.callback().status_code,200)
        with self.factory() as s:
            self.assertTrue(reconcile(s)['passed'])
            ledger=s.scalar(select(p.RewardLedger).where(p.RewardLedger.kind=='reward'))
            outcome=json.loads(ledger.rule_json)['commission_outcomes'][0]
            self.assertEqual((outcome['beneficiary_id'],outcome['eligible']), (parent_id,True))
            self.assertEqual(Decimal(outcome['amount']), Decimal('.1'))
            # Restore the original balance as well: neither the balance nor a
            # surviving commission/log can reveal this complete loss on its own.
            s.query(p.RewardLedger).filter(p.RewardLedger.kind=='commission_1').delete()
            s.query(m.CoinLog).filter(m.CoinLog.type==301).delete()
            s.get(m.Member,parent_id).coin=0
            s.commit()
            report=reconcile(s)
            self.assertFalse(report['passed'])
            self.assertEqual([f['kind'] for f in report['findings']], ['expected_commission_missing'])
            self.assertEqual(report['findings'][0]['beneficiary_id'], parent_id)
            self.assertFalse(s.dirty)

    def test_settlement_links_are_auditable_and_corruption_is_detected(self):
        from app.wallet_audit import reconcile
        from app import member_policy as p
        with self.factory() as s:
            s.get(m.Game,1).settings_json=json.dumps({'member_policy':{'reward_enabled':True,
                'reward_basis':'fixed_ecpm','fixed_ecpm':'1000','commission_rates':['0','.1','0','0']}})
            parent=m.Member(username='audit-parent',game_id=1,agent_id=1,coin=0)
            s.add(parent);s.flush()
            p.enrollment(s,parent).level=1
            p.enrollment(s,s.get(m.Member,self.uid)).parent_id=parent.id
            s.commit()
        self.assertEqual(self.callback().status_code,200)
        with self.factory() as s:
            rows=s.scalars(select(p.RewardLedger)).all()
            self.assertTrue(all(r.coin_log_id for r in rows))
            self.assertTrue(reconcile(s)['passed'])
            commission=next(r for r in rows if r.kind=='commission_1')
            commission.amount=Decimal('10');s.commit()
            self.assertIn('reward_credit_mismatch',{x['kind'] for x in reconcile(s)['findings']})
            commission.amount=Decimal('.1');commission.coin_log_id=None;s.commit()
            self.assertTrue(reconcile(s)['passed']) # legacy exact business-key matching
            s.query(m.CoinLog).filter(m.CoinLog.type==301).delete();s.commit()
            self.assertIn('reward_missing_credit',{x['kind'] for x in reconcile(s)['findings']})
    def test_missing_ecpm_configuration_blocks_admission(self):
        with self.factory() as s:
            s.get(m.Game,1).settings_json=json.dumps({'ad_config':{'provider':'taku','enabled':True,
                'placements':{'rewarded':{'unit_id':'placement-test'}}},'member_policy':{
                'reward_enabled':True,'tier_enabled':True,'ecpm_tiers':[{'upper':50,'percent':200}]}})
            s.commit()
        with patch.dict(os.environ, TAKU_ECPM_KEYRING_FILE=''):
            r=self.client.post('/api/app/v1/ads/request',headers={'Authorization':'Bearer '+self.access},
                json={'game_id':1,'device_id':'test-device','client_request_id':'missing-config'})
        self.assertEqual(r.status_code,503,r.text)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AppAdSession)),1)

    def test_ecpm_readiness_valid_and_invalid_keyring(self):
        from app.taku_ecpm import require_configuration, EcpmConfigurationError
        self.configure_ecpm()
        self.assertTrue(require_configuration(1,required=True))
        with self.assertRaises(EcpmConfigurationError): require_configuration(2,required=True)
        with patch.dict(os.environ,TAKU_ECPM_KEYRING_FILE=str(Path(self.temp.name)/'missing.json')):
            with self.assertRaises(EcpmConfigurationError): require_configuration(1)

    def test_provider_first_impression_retry_preserves_money_and_status(self):
        self.assertEqual(self.callback().status_code,200)
        headers={'Authorization':'Bearer '+self.access}
        body={'session_token':self.token,'event_id':'late-impression'}
        for _ in range(2):
            r=self.client.post('/api/app/v1/ads/ads_test/impression',headers=headers,json=body)
            self.assertEqual(r.status_code,202,r.text)
        with self.factory() as s:
            ad=s.get(m.AppAdSession,'ads_test')
            self.assertEqual(ad.status,'rewarded')
            self.assertIsNotNone(ad.impressed_at)
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AppAdEvent).where(m.AppAdEvent.event_id=='late-impression')),1)
        self.assertEqual(self.balances(),(12,1,1))

    def test_policy_commission_retry_settles_once(self):
        from app import member_policy as policy
        with self.factory() as s:
            game=s.get(m.Game,1)
            game.settings_json=json.dumps({'member_policy':{'reward_enabled':True,'reward_basis':'fixed_ecpm',
                'fixed_ecpm':'1000','commission_rates':['0','.1','0','0']}})
            parent=m.Member(username='parent',game_id=1,agent_id=1,coin=0)
            s.add(parent);s.flush();pid=parent.id
            policy.enrollment(s,parent).level=1
            policy.enrollment(s,s.get(m.Member,self.uid)).parent_id=pid
            s.commit()
        params=self.params()
        self.assertEqual(self.callback(params).status_code,200)
        self.assertEqual(self.callback(params).status_code,200)
        with self.factory() as s:
            self.assertEqual(s.get(m.Member,self.uid).coin,11)
            self.assertEqual(s.get(m.Member,pid).coin,Decimal(".1"))
            self.assertEqual(len(s.scalars(select(policy.RewardLedger)).all()),2)

    def configure_ecpm(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        filename = Path(self.temp.name) / 'keyring.json'
        filename.write_text(json.dumps({'1': {'keys': {'test-key': pem}}}), encoding='utf-8')
        env = patch.dict(os.environ, TAKU_ECPM_KEYRING_FILE=str(filename))
        env.start(); self.addCleanup(env.stop)
        return lambda plain: base64.b64encode(key.public_key().encrypt(plain.encode(), padding.PKCS1v15())).decode()

    def test_encrypted_ecpm_callback_and_retry(self):
        encrypt = self.configure_ecpm()
        p = self.params(e_c=encrypt('123_20.25_sdk-request'),
                        e_c_cny=encrypt('123_140.75_sdk-request'), s_id='test-key')
        self.assertEqual(self.callback(p).status_code, 200)
        self.assertEqual(self.callback(p).status_code, 200)
        with self.factory() as s:
            event = s.scalar(select(m.AppAdEvent).where(m.AppAdEvent.event_type == 'taku_reward'))
            proof = json.loads(event.result_json)['ecpm_verification']
            self.assertEqual([x['ecpm'] for x in proof['prices']], ['20.25', '140.75'])
            self.assertEqual(proof['prices'][0]['sdk_request_id'], 'sdk-request')
        self.assertEqual(self.balances(), (12, 1, 1))

    def test_encrypted_ecpm_invalid_missing_and_wrong_source(self):
        encrypt = self.configure_ecpm()
        for changes in [{}, {'e_c': 'invalid', 's_id': 'test-key'},
                        {'e_c': encrypt('999_1'), 's_id': 'test-key'},
                        {'e_c': encrypt('123_1'), 's_id': 'wrong-key'},
                        {'e_c': encrypt('123_NaN'), 's_id': 'test-key'},
                        {'e_c': encrypt('123_1_a'), 'e_c_cny': encrypt('123_7_b'), 's_id': 'test-key'}]:
            self.assertEqual(self.callback(self.params(**changes)).status_code, 400)
            self.assertEqual(self.balances(), (10, 0, 0))

    def test_fixed_price_encrypted_ecpm_without_request_id(self):
        encrypt = self.configure_ecpm()
        self.assertEqual(self.callback(self.params(e_c=encrypt('123_0'), s_id='test-key')).status_code, 200)

    def test_ecpm_request_cannot_be_reused_for_another_session(self):
        encrypt = self.configure_ecpm()
        self.assertEqual(self.callback(self.params(e_c=encrypt('123_5_sdk-one'), s_id='test-key')).status_code, 200)
        with self.factory() as s:
            ad = m.AppAdSession(id='ads_second', member_id=self.uid, agent_id=1, game_id=1,
                provider='taku', ad_unit_id='placement-test', reward_coin=2, request_id='req-second',
                session_token_hash=m._token_hash(self.token), expires_at=m.now()+timedelta(minutes=5))
            s.add(ad); s.commit(); extra = m._taku_extra_data(ad)
        # A fresh encryption of the same provider request must still be rejected.
        response = self.callback(self.params(trans_id='second', extra_data=extra,
            e_c=encrypt('123_5_sdk-one'), s_id='test-key'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.balances(), (12, 1, 1))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'test.db'), connect_args={'check_same_thread': False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patch = patch.multiple(m, SessionLocal=self.factory, TAKU_SEC_KEY='test-taku-key')
        self.patch.start()
        self.client = TestClient(m.app)
        with self.factory() as s:
            member = m.Member(username='callback-user', coin=10, coin_user=10, agent_id=1, game_id=1)
            s.add(member); s.flush(); self.uid = member.id
            s.add(m.Game(id=1, name='test', agent_id=1))
            self.token = 'session-token-for-test-only'
            ad = m.AppAdSession(id='ads_test', member_id=self.uid, agent_id=1, game_id=1,
                provider='taku', ad_unit_id='placement-test', reward_coin=2, request_id='req-test',
                session_token_hash=m._token_hash(self.token), expires_at=m.now()+timedelta(minutes=5))
            s.add(ad); s.commit(); self.extra = m._taku_extra_data(ad)
            self.access = m._create_app_access_token(member)

    def tearDown(self):
        self.client.close(); self.patch.stop(); self.engine.dispose(); self.temp.cleanup()

    def params(self, **changes):
        p = dict(user_id=str(self.uid), trans_id='transaction-1', placement_id='placement-test',
                 adsource_id='123', reward_amount='2000', reward_name='coin', extra_data=self.extra)
        p.update(changes)
        raw = '&'.join(f'{k}={p[k]}' for k in ['trans_id','placement_id','adsource_id','reward_amount','reward_name'])
        raw += '&sec_key=test-taku-key'
        if 'ilrd' in p: raw += '&ilrd=' + p['ilrd']
        p['sign'] = hashlib.md5(raw.encode()).hexdigest()
        return p

    def callback(self, params=None):
        return self.client.get('/api/callbacks/taku/reward', params=params or self.params())

    def balances(self):
        with self.factory() as s:
            return (s.get(m.Member,self.uid).coin, s.scalar(select(func.count()).select_from(m.CoinLog)),
                    s.scalar(select(func.count()).select_from(m.AdRecord)))

    def completion_payload(self, **changes):
        payload = dict(event_id='client-event', session_token=self.token,
            publisher_revenue_cny='2', sdk_request_id='sdk-request-1',
            sdk_show_id='sdk-show-1', source_id='123')
        payload.update(changes)
        return payload

    def test_settlement_retry_and_record_visibility(self):
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.balances(),(12,1,1))
        with self.factory() as s:
            row=s.scalar(select(m.AdRecord))
            self.assertEqual(row.trans_id,'transaction-1')
            self.assertEqual(row.request_id,'req-test')
            self.assertEqual(row.ecpm,2000)
        self.assertEqual(self.callback(self.params(trans_id='transaction-2')).status_code,400)
        self.assertEqual(self.balances(),(12,1,1))

    def test_invalid_signature_binding_and_disabled_configuration(self):
        p=self.params();p['sign']='0'*32
        self.assertEqual(self.callback(p).status_code,403)
        for changes in [dict(extra_data='ads_test'),dict(user_id='999'),dict(placement_id='other')]:
            self.assertEqual(self.callback(self.params(**changes)).status_code,400)
        with patch.object(m,'TAKU_SEC_KEY',''):
            self.assertEqual(self.callback().status_code,503)
        self.assertEqual(self.balances(),(10,0,0))

    def test_console_probe_never_settles(self):
        self.assertEqual(self.callback({'is_test':'1','sign':'{sign}'}).status_code,200)
        self.assertEqual(self.balances(),(10,0,0))

    def test_ilrd_signature_including_empty_string(self):
        self.assertEqual(self.callback(self.params(ilrd='')).status_code,200)
        self.assertEqual(self.callback(self.params(ilrd='{"currency":"USD"}')).status_code,200)
        self.assertEqual(self.balances(),(12,1,1))

    def test_client_completion_rewards_immediately_and_is_idempotent(self):
        payload=self.completion_payload()
        headers={'Authorization':'Bearer '+self.access}
        r=self.client.post('/api/app/v1/ads/ads_test/complete',json=payload,headers=headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(r.json()['data']['rewarded'])
        self.assertEqual(r.json()['data']['coin_added'],2)
        self.assertEqual(r.json()['data']['coin_balance'],12)
        self.assertEqual(self.balances(),(12,1,1))
        retry=self.client.post('/api/app/v1/ads/ads_test/complete',json=payload,headers=headers)
        self.assertEqual(retry.status_code,200,retry.text)
        self.assertEqual(retry.json()['data']['coin_log_id'],r.json()['data']['coin_log_id'])
        self.assertEqual(self.balances(),(12,1,1))
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.balances(),(12,1,1))

    def test_client_completion_uses_publisher_revenue_and_policy_multiplier(self):
        with self.factory() as s:
            s.get(m.Game,1).settings_json=json.dumps({'member_policy':{
                'reward_enabled':True,'reward_basis':'fixed_ecpm','fixed_ecpm':'500',
                'coins_per_yuan':'10'}})
            s.commit()
        response=self.client.post('/api/app/v1/ads/ads_test/complete',
            headers={'Authorization':'Bearer '+self.access},
            json=self.completion_payload(publisher_revenue_cny='0.2'))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['data']['coin_added'],2)
        self.assertEqual(self.balances(),(12,1,1))
        from app.member_policy import RewardLedger
        with self.factory() as s:
            ledger=s.scalar(select(RewardLedger).where(RewardLedger.kind=='reward'))
            detail=json.loads(ledger.rule_json)
            self.assertEqual(detail['reward_mode'],'publisher_revenue')
            self.assertEqual(detail['publisher_revenue_cny'],'0.2')

    def test_client_completion_requires_revenue_and_unique_provider_identity(self):
        headers={'Authorization':'Bearer '+self.access}
        missing=self.client.post('/api/app/v1/ads/ads_test/complete',headers=headers,
            json={'event_id':'missing','session_token':self.token})
        self.assertEqual(missing.status_code,422,missing.text)
        self.assertEqual(missing.json()['detail']['code'],'PUBLISHER_REVENUE_REQUIRED')
        first=self.client.post('/api/app/v1/ads/ads_test/complete',headers=headers,
            json=self.completion_payload())
        self.assertEqual(first.status_code,200,first.text)
        with self.factory() as s:
            other=m.AppAdSession(id='ads_other',member_id=self.uid,agent_id=1,game_id=1,
                provider='taku',ad_unit_id='placement-test',reward_coin=99,request_id='req-other',
                session_token_hash=m._token_hash(self.token),expires_at=m.now()+timedelta(minutes=5))
            s.add(other);s.commit()
        replay=self.client.post('/api/app/v1/ads/ads_other/complete',headers=headers,
            json=self.completion_payload(event_id='client-event-other',sdk_show_id='different-show'))
        self.assertEqual(replay.status_code,409,replay.text)
        self.assertEqual(replay.json()['detail']['code'],'PUBLISHER_REVENUE_ALREADY_USED')
        self.assertEqual(self.balances(),(12,1,1))

    def test_concurrent_client_completions_credit_only_once(self):
        headers={'Authorization':'Bearer '+self.access}
        payload=self.completion_payload()
        with ThreadPoolExecutor(max_workers=5) as pool:
            responses=list(pool.map(lambda _:self.client.post('/api/app/v1/ads/ads_test/complete',
                json=payload,headers=headers),range(5)))
        self.assertEqual([r.status_code for r in responses],[200]*5)
        self.assertTrue(all(r.json()['data']['rewarded'] for r in responses))
        self.assertEqual(self.balances(),(12,1,1))

    def test_client_reward_callback_bad_signature_still_rejected(self):
        self.assertEqual(self.client.post('/api/app/v1/ads/ads_test/complete',
            headers={'Authorization':'Bearer '+self.access},
            json=self.completion_payload()).status_code,200)
        params=self.params();params['sign']='0'*32
        self.assertEqual(self.callback(params).status_code,403)
        self.assertEqual(self.balances(),(12,1,1))

    def test_client_reward_callback_with_valid_ecpm_updates_audit_only(self):
        self.assertEqual(self.client.post('/api/app/v1/ads/ads_test/complete',
            headers={'Authorization':'Bearer '+self.access},
            json=self.completion_payload()).status_code,200)
        encrypt=self.configure_ecpm()
        params=self.params(e_c_cny=encrypt('123_20.5_sdk-callback'),s_id='test-key')
        self.assertEqual(self.callback(params).status_code,200)
        self.assertEqual(self.balances(),(12,1,1))
        with self.factory() as s:
            record=s.scalar(select(m.AdRecord))
            self.assertEqual(record.trans_id,'transaction-1')
            self.assertEqual(record.callback_ecpm,20.5)
            self.assertEqual(record.callback_price_currency,'CNY')
            event=s.scalar(select(m.AppAdEvent).where(m.AppAdEvent.event_type=='taku_reconciliation'))
            self.assertTrue(json.loads(event.result_json)['callback_ecpm_verified'])

    def test_late_client_completion_is_accepted_once_within_recovery_window(self):
        with self.factory() as s:
            ad=s.get(m.AppAdSession,'ads_test')
            ad.status='expired';ad.expires_at=m.now()-timedelta(minutes=1)
            s.commit()
        response=self.client.post('/api/app/v1/ads/ads_test/complete',
            headers={'Authorization':'Bearer '+self.access},
            json=self.completion_payload())
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['data']['rewarded'])
        self.assertEqual(self.balances(),(12,1,1))

    def test_actual_settlement_overrides_configured_reward_in_responses(self):
        self.assertEqual(self.callback(self.params(reward_amount='1')).status_code, 200)
        headers = {'Authorization': 'Bearer ' + self.access}
        history = self.client.get('/api/app/v1/ads/history', headers=headers)
        self.assertEqual(history.json()['data']['items'][0]['coin_added'], 0.001)
        complete = self.client.post('/api/app/v1/ads/ads_test/complete',
            json=dict(event_id='settled-complete', session_token=self.token), headers=headers)
        self.assertEqual(complete.json()['data']['coin_added'], 0.001)
        self.assertEqual(self.balances()[0], Decimal('10.001000'))

    def test_concurrent_callbacks_only_settle_once(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            codes=list(pool.map(lambda _:self.callback().status_code,range(5)))
        self.assertEqual(codes,[200]*5)
        self.assertEqual(self.balances(),(12,1,1))

    def test_failed_session_does_not_settle(self):
        with self.factory() as s:
            s.get(m.AppAdSession,'ads_test').status='failed';s.commit()
        self.assertEqual(self.callback().status_code,400)
        self.assertEqual(self.balances(),(10,0,0))

    def test_late_provider_delivery_after_client_expiration(self):
        with self.factory() as s:
            ad=s.get(m.AppAdSession,'ads_test');ad.status='expired';ad.expires_at=m.now()-timedelta(minutes=1);s.commit()
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.balances(),(12,1,1))

    def test_transaction_cannot_be_reassigned_to_another_session(self):
        self.assertEqual(self.callback().status_code,200)
        with self.factory() as s:
            ad=m.AppAdSession(id='ads_other', member_id=self.uid, agent_id=1, game_id=1,
                provider='taku', ad_unit_id='placement-test', reward_coin=2, request_id='req-other',
                session_token_hash=m._token_hash(self.token), expires_at=m.now()+timedelta(minutes=5))
            s.add(ad);s.commit();extra=m._taku_extra_data(ad)
        self.assertEqual(self.callback(self.params(extra_data=extra)).status_code,400)
        self.assertEqual(self.balances(),(12,1,1))

    def test_request_returns_sdk_context_and_blocks_missing_secret(self):
        import json
        with self.factory() as s:
            game=s.get(m.Game,1)
            game.settings_json=json.dumps({'ad_config':{'provider':'taku','enabled':True,'placements':{'rewarded':{'unit_id':'placement-test','reward_coin':2}}}})
            s.commit()
        headers={'Authorization':'Bearer '+self.access}
        payload={'game_id':1,'device_id':'test-device','client_request_id':'new-client-request'}
        r=self.client.post('/api/app/v1/ads/request',headers=headers,json=payload)
        self.assertEqual(r.status_code,201,r.text)
        data=r.json()['data']
        self.assertEqual(data['reward_verification'],'client_publisher_revenue_with_server_reconciliation')
        self.assertEqual(data['taku_user_id'],str(self.uid))
        self.assertTrue(data['taku_extra_data'].startswith(data['ad_session_id']+'.'))
        self.assertNotIn('test-taku-key',r.text)
        with patch.object(m,'TAKU_SEC_KEY',''):
            r=self.client.post('/api/app/v1/ads/request',headers=headers,json=payload)
            self.assertEqual(r.status_code,503)

    def test_non_ascii_and_duplicate_signature_rejected(self):
        p=self.params();p['sign']='\u4e2d'
        self.assertEqual(self.callback(p).status_code,403)
        pairs=list(self.params().items())+[('sign','duplicate')]
        self.assertEqual(self.callback(pairs).status_code,400)
        self.assertEqual(self.balances(),(10,0,0))

    def test_game_private_key_save_preserve_clear_and_no_leak(self):
        data=dict(provider='taku',rewarded_unit_id='placement-test',taku_callback_enabled=1,taku_sec_key='private-game-key')
        result=m.update_game_ad_config(1,m.GameAdConfigUpdate(**data))
        self.assertTrue(result['taku_sec_key_configured'])
        self.assertNotIn('private-game-key',str(result))
        data['taku_sec_key']=''
        m.update_game_ad_config(1,m.GameAdConfigUpdate(**data))
        with self.factory() as s:
            self.assertEqual(m.taku_credentials(s,1),(True,'private-game-key'))
            self.assertNotIn('private-game-key',s.get(m.Game,1).settings_json)
            self.assertNotIn('private-game-key',str(m.serialize_game_editor(s.get(m.Game,1))))
        self.assertEqual(self.callback().status_code,403)  # Global key cannot override game key.
        p=self.params()
        raw='&'.join(f'{k}={p[k]}' for k in ['trans_id','placement_id','adsource_id','reward_amount','reward_name'])+'&sec_key=private-game-key'
        p['sign']=hashlib.md5(raw.encode()).hexdigest()
        self.assertEqual(self.callback(p).status_code,200)
        data.update(taku_callback_enabled=0,taku_clear_sec_key=True)
        result=m.update_game_ad_config(1,m.GameAdConfigUpdate(**data))
        self.assertFalse(result['taku_sec_key_configured'])
        self.assertEqual(self.callback(p).status_code,503)

    def test_disabled_game_does_not_fall_back_to_global_key(self):
        with self.factory() as s:
            s.add(m.GameTakuConfig(game_id=1,enabled=0,sec_key='own-key'))
            s.add(m.GameTakuConfig(game_id=2,enabled=1,sec_key='other-key'));s.commit()
            self.assertEqual(m.taku_credentials(s,2),(True,'other-key'))
        self.assertEqual(self.callback().status_code,503)
        self.assertEqual(self.balances(),(10,0,0))

    def test_cannot_enable_without_key_and_rolls_back(self):
        from fastapi import HTTPException
        with patch.object(m,'TAKU_SEC_KEY',''):
            with self.assertRaises(HTTPException):
                m.update_game_ad_config(1,m.GameAdConfigUpdate(provider='taku',rewarded_unit_id='placement-test',taku_callback_enabled=1))
        with self.factory() as s:
            self.assertIsNone(s.get(m.GameTakuConfig,1))


if __name__ == '__main__':
    unittest.main()
