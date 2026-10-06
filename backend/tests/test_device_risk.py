"""Device risk admission tests, isolated DB and mocked cloud transport."""
import os
import sys
import tempfile
import unittest
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs
from io import BytesIO

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class DeviceRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global m, r
        from app import main_from_txt as m
        from app import device_risk as r

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'risk.db'), connect_args={'check_same_thread': False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patches = [patch.object(m, 'SessionLocal', self.factory), patch.object(m, 'APP_ENV', 'development'),
            patch.dict(os.environ, {'ALIBABA_CLOUD_ACCESS_KEY_ID': 'test-key', 'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'test-secret'})]
        for p in self.patches: p.start()
        self.client = TestClient(m.app)
        with self.factory() as s:
            s.add(m.Agent(id=1, name='Agent'))
            s.add(m.Game(id=1, agent_id=1, name='Game'))
            for i in (1, 2): s.add(m.Member(id=i, username=f'user{i}', agent_id=1, game_id=1))
            for i, role in ((1, 'risk'), (2, 'reviewer')):
                s.add(m.AdminUser(id=i, username=role, role=role, status=1, password_hash='unused', password_salt='unused'))
            s.add(r.DeviceRule(game_id=1, enabled=1, limit_enabled=1, daily_limit=2))
            s.commit()
            self.auth = {'Authorization': 'Bearer ' + m._create_app_access_token(s.get(m.Member, 1))}
            self.other = {'Authorization': 'Bearer ' + m._create_app_access_token(s.get(m.Member, 2))}
            self.admin = {'Authorization': 'Bearer ' + m.create_access_token(s.get(m.AdminUser, 1))}
            self.reviewer = {'Authorization': 'Bearer ' + m.create_access_token(s.get(m.AdminUser, 2))}

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches): p.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def challenge(self, install='installation-uuid-0001', auth=None):
        res = self.client.post('/api/app/v1/device-risk/challenge', headers=auth or self.auth, json={'game_id': 1, 'install_id': install})
        self.assertEqual(res.status_code, 201, res.text)
        return res.json()['data']['challenge_id']

    def verify(self, install='installation-uuid-0001', auth=None, device='verified-device-A', tags=None):
        cid = self.challenge(install, auth)
        with patch.object(r, 'aliyun_check', return_value=(device, tags or [], 'aliyun-request')) as mock:
            res = self.client.post('/api/app/v1/device-risk/verify', headers=auth or self.auth,
                json={'challenge_id': cid, 'aliyun_device_token': 'sdk-token-example'})
            mock.assert_called_once_with('sdk-token-example', cid)
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()['data']

    def ad(self, check='', auth=None, key=''):
        return self.client.post('/api/app/v1/ads/request', headers=auth or self.auth,
            json={'game_id': 1, 'device_id': 'untrusted-client-id', 'risk_check_id': check, 'client_request_id': key})

    def test_reset_and_shared_device_quota(self):
        first = self.verify()
        self.assertFalse(first['suspected_reset'])
        self.assertEqual(self.ad(first['risk_check_id']).status_code, 201)
        second = self.verify('installation-uuid-0002', self.other)
        self.assertTrue(second['suspected_reset'])
        self.assertEqual(second['remaining'], 1)
        self.assertEqual(self.ad(second['risk_check_id'], self.other).status_code, 201)
        third = self.verify()
        self.assertEqual(self.ad(third['risk_check_id']).status_code, 429)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AppAdSession)), 2)
            self.assertEqual(s.scalar(select(func.count()).select_from(r.DeviceAdAdmission)), 2)

    def test_missing_receipt_replay_ownership_and_retry(self):
        self.assertEqual(self.ad().status_code, 403)
        receipt = self.verify()['risk_check_id']
        self.assertEqual(self.ad(receipt, self.other).status_code, 403)
        first = self.ad(receipt, key='same-request')
        self.assertEqual(first.status_code, 201, first.text)
        retry = self.ad(receipt, key='same-request')
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(first.json()['data']['ad_session_id'], retry.json()['data']['ad_session_id'])
        self.assertEqual(self.ad(receipt).status_code, 403)
        self.assertEqual(self.ad(key='same-request').status_code, 403)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(r.DeviceAdAdmission)), 1)

    def test_switches_zero_limit_override_and_permissions(self):
        rule = {'enabled': True, 'limit_enabled': True, 'daily_limit': 0, 'reset_tags': ['reset_confirmed']}
        path = '/api/v1/games/1/device-risk'
        self.assertEqual(self.client.put(path, headers=self.reviewer, json=rule).status_code, 403)
        self.assertEqual(self.client.put(path, headers=self.admin, json=rule).status_code, 200)
        check = self.verify(tags=['reset_confirmed'])
        self.assertEqual(self.ad(check['risk_check_id']).status_code, 429)
        res = self.client.patch(f"/api/v1/device-risk/devices/{check['device_id']}", headers=self.admin,
            json={'mode': 'allow', 'reason': '已核实为正常重装'})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.ad(check['risk_check_id']).status_code, 201)
        self.assertEqual(self.client.put(path, headers=self.admin, json={'enabled': False}).status_code, 200)
        self.assertEqual(self.ad().status_code, 201)
        listed = self.client.get('/api/v1/device-risk/devices?game_id=1', headers=self.admin)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(listed.json()['total'], 1)

    def test_cloud_failure_and_expired_challenge(self):
        cid = self.challenge()
        body = {'challenge_id': cid, 'aliyun_device_token': 'sdk-token-example'}
        self.assertEqual(self.client.post('/api/app/v1/device-risk/verify', headers=self.other, json=body).status_code, 404)
        with patch.object(r, 'aliyun_check', side_effect=HTTPException(503, 'cloud unavailable')):
            self.assertEqual(self.client.post('/api/app/v1/device-risk/verify', headers=self.auth, json=body).status_code, 503)
        self.assertEqual(self.ad(cid).status_code, 403)
        self.assertEqual(self.client.post('/api/app/v1/device-risk/verify', headers=self.auth, json=body).status_code, 409)
        cid = self.challenge()
        with self.factory() as s:
            s.get(r.DeviceCheck, cid).expires_at = m.now() - timedelta(seconds=1); s.commit()
        body['challenge_id'] = cid
        with patch.object(r, 'aliyun_check') as mock:
            self.assertEqual(self.client.post('/api/app/v1/device-risk/verify', headers=self.auth, json=body).status_code, 409)
            mock.assert_not_called()

    def test_concurrent_last_slot(self):
        self.verify()
        a = self.verify('installation-uuid-0002')['risk_check_id']
        b = self.verify('installation-uuid-0002')['risk_check_id']
        with self.factory() as s:
            s.get(r.DeviceRule, 1).daily_limit = 1; s.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(lambda c: self.ad(c).status_code, [a, b]))
        self.assertEqual(sorted(codes), [201, 429])

    def test_old_install_not_reflagged_and_new_device_not_reset(self):
        self.verify()
        second = self.verify('installation-uuid-0002')
        with self.factory() as s:
            s.get(r.RiskDevice, second['device_id']).risk_until = m.now() - timedelta(days=1); s.commit()
        self.assertFalse(self.verify()['suspected_reset'])
        self.assertFalse(self.verify(device='another-phone')['suspected_reset'])

    def test_rpc_payload_and_reject_missing_fingerprint(self):
        data = {'Code': 200, 'Data': json.dumps({'extend': 'cloud-device', 'tags': 'is_rooted,is_emulator'}), 'RequestId': 'cloud-id'}
        with patch.object(r, 'urlopen', return_value=BytesIO(json.dumps(data).encode())) as mock:
            result = r.aliyun_check('token-long-enough', 'biz-123')
            req = mock.call_args.args[0]
            params = parse_qs(req.data.decode())
            self.assertEqual(params['Service'], ['device_risk_pro'])
            self.assertEqual(json.loads(params['ServiceParameters'][0]), {'deviceToken': 'token-long-enough', 'deviceTokenBizId': 'biz-123'})
            self.assertTrue(params['Signature'][0])
            self.assertEqual(result[0], 'cloud-device')
        with patch.object(r, 'urlopen', return_value=BytesIO(b'{"Code":200,"Data":{"tags":""}}')):
            with self.assertRaises(HTTPException) as error: r.aliyun_check('token', 'biz')
            self.assertEqual(error.exception.status_code, 503)

    def test_quota_day_and_detection_only(self):
        self.verify()
        check = self.verify('installation-uuid-0002')['risk_check_id']
        self.assertEqual(self.ad(check).status_code, 201)
        with self.factory() as s:
            s.get(r.DeviceRule, 1).daily_limit = 1
            s.scalar(select(r.DeviceAdAdmission)).quota_date -= timedelta(days=1)
            s.commit()
        self.assertEqual(self.ad(self.verify()['risk_check_id']).status_code, 201)
        with self.factory() as s:
            s.get(r.DeviceRule, 1).limit_enabled = 0; s.commit()
        self.assertEqual(self.ad(self.verify()['risk_check_id']).status_code, 201)


if __name__ == '__main__': unittest.main()
