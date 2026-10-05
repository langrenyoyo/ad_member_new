"""TAKU callbacks exercise a temporary database; never contact the live provider."""
import hashlib
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app import main_from_txt as m


class TakuCallbackTests(unittest.TestCase):
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
                 adsource_id='123', reward_amount='9999', reward_name='coin', extra_data=self.extra)
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

    def test_settlement_retry_and_record_visibility(self):
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.callback().status_code,200)
        self.assertEqual(self.balances(),(12,1,1))
        with self.factory() as s:
            row=s.scalar(select(m.AdRecord))
            self.assertEqual(row.trans_id,'transaction-1')
            self.assertEqual(row.request_id,'req-test')
            self.assertEqual(row.ecpm,0)  # Never invent provider revenue from reward amount.
        self.assertEqual(self.callback(self.params(trans_id='transaction-2')).status_code,602)
        self.assertEqual(self.balances(),(12,1,1))

    def test_invalid_signature_binding_and_disabled_configuration(self):
        p=self.params();p['sign']='0'*32
        self.assertEqual(self.callback(p).status_code,601)
        for changes in [dict(extra_data='ads_test'),dict(user_id='999'),dict(placement_id='other')]:
            self.assertEqual(self.callback(self.params(**changes)).status_code,602)
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

    def test_client_completion_waits_for_callback(self):
        payload=dict(event_id='client-event',session_token=self.token)
        headers={'Authorization':'Bearer '+self.access}
        r=self.client.post('/api/app/v1/ads/ads_test/complete',json=payload,headers=headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertFalse(r.json()['data']['rewarded'])
        self.assertEqual(r.json()['data']['message'],'奖励确认中')
        self.assertNotIn('coin_added',r.json()['data'])
        self.assertEqual(self.balances(),(10,0,0))
        self.assertEqual(self.callback().status_code,200)
        r=self.client.post('/api/app/v1/ads/ads_test/complete',json=payload,headers=headers)
        self.assertTrue(r.json()['data']['rewarded'])
        self.assertEqual(self.balances(),(12,1,1))

    def test_concurrent_callbacks_only_settle_once(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            codes=list(pool.map(lambda _:self.callback().status_code,range(5)))
        self.assertEqual(codes,[200]*5)
        self.assertEqual(self.balances(),(12,1,1))

    def test_failed_session_does_not_settle(self):
        with self.factory() as s:
            s.get(m.AppAdSession,'ads_test').status='failed';s.commit()
        self.assertEqual(self.callback().status_code,602)
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
        self.assertEqual(self.callback(self.params(extra_data=extra)).status_code,602)
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
        self.assertEqual(data['reward_verification'],'server_callback')
        self.assertEqual(data['taku_user_id'],str(self.uid))
        self.assertTrue(data['taku_extra_data'].startswith(data['ad_session_id']+'.'))
        self.assertNotIn('test-taku-key',r.text)
        with patch.object(m,'TAKU_SEC_KEY',''):
            r=self.client.post('/api/app/v1/ads/request',headers=headers,json=payload)
            self.assertEqual(r.status_code,503)

    def test_non_ascii_and_duplicate_signature_rejected(self):
        p=self.params();p['sign']='\u4e2d'
        self.assertEqual(self.callback(p).status_code,601)
        pairs=list(self.params().items())+[('sign','duplicate')]
        self.assertEqual(self.callback(pairs).status_code,602)
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
        self.assertEqual(self.callback().status_code,601)  # Global key cannot override game key.
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
