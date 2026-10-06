import base64
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeAlipay:
    available = True
    name = 'alipay'
    def __init__(self, result):
        self.result = result
        self.sends = []
        self.queries = []
    def send(self, order):
        self.sends.append(order)
        return self.result
    def query(self, order):
        self.queries.append(order)
        return self.result
    def verify_notification(self, params):
        return params.get('sign') == 'test-only-valid'


class AlipayPayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global m, payment
        from app import main_from_txt as m
        from app import payment

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'test.db'),
            connect_args={'check_same_thread': False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patcher = patch.object(m, 'SessionLocal', self.factory)
        self.patcher.start()
        self.provider = FakeAlipay(payment.PaymentResult('succeeded', order_id='ALIPAY-ORDER-1'))
        self.provider_patch = patch.object(m, 'configured_provider', return_value=self.provider)
        self.provider_patch.start()
        self.client = TestClient(m.app)
        with self.factory() as session:
            hashed, salt = m.hash_password('User-Password-123')
            self.user = m.Member(id=1, username='withdraw-user', password_hash=hashed, password_salt=salt,
                                 coin=100, freeze_coin=0, game_id=1, agent_id=1)
            other = m.Member(id=2, username='other', game_id=1, agent_id=1)
            admin = m.AdminUser(username='admin', password_hash='unused', password_salt='unused', role='superadmin')
            session.add_all([self.user, other, admin, m.Agent(id=1, name='Agent'),
                m.Game(id=1, agent_id=1, name='Game', tixian_price='5,10', tixian_coin='20,40', exchange_num=10)])
            session.commit()
            self.auth = {'Authorization': 'Bearer ' + m._create_app_access_token(self.user)}
            self.other_auth = {'Authorization': 'Bearer ' + m._create_app_access_token(other)}
            self.admin_auth = {'Authorization': 'Bearer ' + m.create_access_token(admin)}
        self.binding = dict(account='13000000000', real_name='测试用户', current_password='User-Password-123')
        bound = self.client.put('/api/app/v1/me/alipay', json=self.binding, headers=self.auth)
        self.assertEqual(bound.status_code, 200, bound.text)
        self.body = dict(request_key='request-001', game_id=1, amount_cents=500)

    def tearDown(self):
        self.client.close()
        self.provider_patch.stop()
        self.patcher.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def apply(self, **kwargs):
        return self.client.post('/api/app/v1/withdrawals', json={**self.body, **kwargs}, headers=self.auth)

    def balance(self):
        with self.factory() as session:
            user = session.get(m.Member, 1)
            return user.coin, user.freeze_coin

    def approve(self, wid):
        r = self.client.post(f'/api/v1/withdrawals/{wid}/approve', headers=self.admin_auth)
        self.assertEqual(r.status_code, 200, r.text)

    def test_apply_freeze_success_query_and_duplicate(self):
        r = self.apply()
        self.assertEqual(r.status_code, 201, r.text)
        wid = r.json()['data']['id']
        self.assertEqual(self.balance(), (80, 20))
        self.assertEqual(self.apply().json()['data']['id'], wid)
        self.assertEqual(self.balance(), (80, 20))
        self.assertEqual(self.apply(amount_cents=1000).status_code, 409)
        self.assertEqual(self.client.put('/api/app/v1/me/alipay', json=self.binding, headers=self.auth).status_code, 409)
        self.approve(wid)
        path = f'/api/v1/withdrawals/{wid}/transfer'
        result = self.client.post(path, headers=self.admin_auth)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['payout']['state'], 'succeeded')
        self.assertEqual(result.json()['plan_status'], 1)
        self.assertIsNotNone(result.json()['transferred_at'])
        self.assertEqual(self.balance(), (80, 0))
        self.assertEqual(self.client.post(path, headers=self.admin_auth).status_code, 200)
        self.assertEqual(len(self.provider.sends), 1)
        own = self.client.get(f'/api/app/v1/withdrawals/{wid}', headers=self.auth).json()['data']
        self.assertEqual(own['payout']['state'], 'succeeded')
        self.assertNotIn('receive_tel', own)
        self.assertEqual(self.client.get(f'/api/app/v1/withdrawals/{wid}', headers=self.other_auth).status_code, 404)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(m.CoinLog)), 2)

    def test_all_rejection_entries_refund_once(self):
        for index, mode in enumerate(['reject', 'refuse', 'batch-reject', 'batch-refuse', 'patch']):
            wid = self.apply(request_key=f'reject-{index:03d}').json()['data']['id']
            path = f'/api/v1/withdrawals/{wid}'
            if mode.startswith('batch'):
                r = self.client.post('/api/v1/withdrawals/'+mode, json={'ids':[wid], 'reason':'Rejected'}, headers=self.admin_auth)
            elif mode == 'patch':
                r = self.client.patch(path, json={'status':2, 'reason':'Rejected'}, headers=self.admin_auth)
            else:
                r = self.client.post(path+'/'+mode, json={'reason':'Rejected'}, headers=self.admin_auth)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(self.balance(), (100, 0))
            self.assertEqual(self.client.post(path+'/reject', json={'reason':'Again'}, headers=self.admin_auth).status_code, 409)
            self.assertEqual(self.balance(), (100, 0))

    def test_timeout_preserves_hold_and_query_settles_once(self):
        self.provider.result = payment.PaymentResult(message='Timeout')
        wid = self.apply().json()['data']['id']
        self.approve(wid)
        path = f'/api/v1/withdrawals/{wid}'
        r = self.client.post(path+'/transfer', headers=self.admin_auth)
        self.assertEqual(r.json()['payout']['state'], 'processing')
        self.assertIsNone(r.json()['transferred_at'])
        self.assertEqual(self.balance(), (80, 20))
        self.client.post(path+'/transfer', headers=self.admin_auth)
        self.assertEqual(len(self.provider.sends), 1)
        self.provider.result = payment.PaymentResult('succeeded', order_id='confirmed')
        result = self.client.post(path+'/query-transfer', headers=self.admin_auth)
        self.assertEqual(result.json()['payout']['state'], 'succeeded')
        self.assertEqual(self.balance(), (80, 0))
        self.client.post(path+'/query-transfer', headers=self.admin_auth)
        self.assertEqual(self.balance(), (80, 0))

    def test_confirmed_failure_refunds_but_unknown_does_not(self):
        wid = self.apply().json()['data']['id']
        self.approve(wid)
        self.provider.result = payment.PaymentResult('failed', 'Confirmed failure')
        result = self.client.post(f'/api/v1/withdrawals/{wid}/transfer', headers=self.admin_auth)
        self.assertEqual(result.json()['payout']['state'], 'failed')
        self.assertEqual(self.balance(), (100, 0))
        self.assertIsNone(result.json()['transferred_at'])
        self.client.post(f'/api/v1/withdrawals/{wid}/retry-transfer', headers=self.admin_auth)
        self.assertEqual(len(self.provider.sends), 1)
        self.assertEqual(self.balance(), (100, 0))

    def test_concurrent_apply_does_not_overdraw(self):
        with self.factory() as session:
            session.get(m.Member, 1).coin = 20
            session.commit()
        barrier = Barrier(2)
        def submit(i):
            client = TestClient(m.app)
            try:
                barrier.wait(timeout=10)
                return client.post('/api/app/v1/withdrawals', json={**self.body, 'request_key':f'concurrent-{i}'}, headers=self.auth).status_code
            finally: client.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(submit, range(2)))
        self.assertEqual(sorted(result), [201, 409])
        self.assertEqual(self.balance(), (0, 20))

    def test_validation_permissions_and_immutable_order(self):
        self.assertEqual(self.apply(amount_cents=501).status_code, 422)
        self.assertEqual(self.apply(coin_cost=1).status_code, 422)
        bad = {**self.binding, 'current_password':'wrong'}
        self.assertEqual(self.client.put('/api/app/v1/me/alipay', json=bad, headers=self.auth).status_code, 401)
        wid = self.apply().json()['data']['id']
        for field, value in [('exchange_value',999),('receive_tel','attacker'),('receive_name','attacker')]:
            self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{wid}', json={field:value}, headers=self.admin_auth).status_code, 422)
        self.approve(wid)
        self.assertEqual(self.client.patch(f'/api/v1/withdrawals/{wid}', json={'plan_status':1}, headers=self.admin_auth).status_code, 409)
        self.assertEqual(self.client.post(f'/api/v1/withdrawals/{wid}/transfer', headers=self.auth).status_code, 401)
        self.assertEqual(self.balance(), (80, 20))

    def test_unconfigured_and_blacklist_never_freeze(self):
        with patch.object(m, 'configured_provider', return_value=payment.PaymentProvider()):
            self.assertEqual(self.apply().status_code, 503)
        self.assertEqual(self.balance(), (100, 0))
        with self.factory() as session:
            session.add(m.WithdrawalBlacklist(receive_name=self.binding['real_name'], receive_tel=self.binding['account']))
            session.commit()
        self.assertEqual(self.apply().status_code, 403)
        self.assertEqual(self.balance(), (100, 0))

    def test_scheduled_queue_and_same_order_retry(self):
        wid = self.apply().json()['data']['id']
        self.approve(wid)
        result = self.client.post('/api/v1/withdrawals/batch-transfer-scheduled', json={'ids':[wid]}, headers=self.admin_auth)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['items'][0]['payout']['state'], 'queued')
        self.assertEqual(len(self.provider.sends), 0)
        self.assertEqual(self.balance(), (80, 20))
        self.provider.result = payment.PaymentResult(message='timeout')
        m.payouts.transfer(wid, None)
        first = self.provider.sends[0]['out_biz_no']
        self.provider.result = payment.PaymentResult('not_found')
        self.client.post(f'/api/v1/withdrawals/{wid}/retry-transfer', headers=self.admin_auth)
        self.assertEqual(len(self.provider.sends), 2)
        self.assertEqual(self.provider.sends[1]['out_biz_no'], first)
        self.assertEqual(self.balance(), (80, 20))

    def test_changed_provider_scope_blocks_transfer(self):
        wid = self.apply().json()['data']['id']
        self.approve(wid)
        self.provider.scope = 'different-app'
        response = self.client.post(f'/api/v1/withdrawals/{wid}/transfer', headers=self.admin_auth)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.provider.sends), 0)
        self.assertEqual(self.balance(), (80, 20))

    def test_callback_never_trusts_unverified_amount_or_status(self):
        wid = self.apply().json()['data']['id']
        self.approve(wid)
        self.provider.result = payment.PaymentResult(message='Timeout')
        result = self.client.post(f'/api/v1/withdrawals/{wid}/transfer', headers=self.admin_auth).json()
        params = {'out_biz_no':result['payout']['out_biz_no'], 'status':'SUCCESS', 'sign':'forged'}
        self.assertEqual(self.client.post('/api/payments/alipay/notify', content=urlencode(params)).status_code, 400)
        self.assertEqual(self.balance(), (80,20))
        params['sign'] = 'test-only-valid'
        self.assertEqual(self.client.post('/api/payments/alipay/notify', content=urlencode(params)).text, 'failure')
        self.assertEqual(self.balance(), (80,20))
        self.provider.result = payment.PaymentResult('succeeded', order_id='confirmed')
        self.assertEqual(self.client.post('/api/payments/alipay/notify', content=urlencode(params)).text, 'success')
        self.assertEqual(self.balance(), (80,0))


class AlipaySignatureTests(unittest.TestCase):
    def setUp(self):
        from app import payment
        self.payment = payment
        self.app_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.alipay_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.provider = payment.AlipayProvider.__new__(payment.AlipayProvider)
        self.provider.app_id = 'test-app'
        self.provider.private_key = self.app_key
        self.provider.public_key = self.alipay_key.public_key()
        self.provider.gateway = 'https://example.invalid'
        self.provider.timeout = 1
        self.order = dict(out_biz_no='order-1', amount_cents=500, account='test@example.com', real_name='测试')

    def response(self, payload, method='alipay.fund.trans.uni.transfer', tamper=False):
        raw = json.dumps(payload, ensure_ascii=False)
        signature = base64.b64encode(self.alipay_key.sign(raw.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
        if tamper: raw = raw.replace('SUCCESS', 'FAIL')
        return BytesIO(('{"'+method.replace('.','_')+'_response":'+raw+',"sign":"'+signature+'"}').encode())

    def test_request_signature_and_original_response_verification(self):
        captured = []
        def server(request, timeout):
            params = {k:v[0] for k,v in parse_qs(request.data.decode()).items()}
            sign = params.pop('sign')
            self.app_key.public_key().verify(base64.b64decode(sign), self.payment.canonical(params).encode(), padding.PKCS1v15(), hashes.SHA256())
            captured.append(json.loads(params['biz_content']))
            return self.response({'code':'10000','status':'SUCCESS','order_id':'alipay-1','out_biz_no':'order-1'})
        with patch.object(self.payment, 'urlopen', side_effect=server):
            result = self.provider.send(self.order)
        self.assertEqual(result.state, 'succeeded')
        self.assertEqual(captured[0]['trans_amount'], '5.00')
        self.assertEqual(captured[0]['payee_info']['name'], '测试')

    def test_tampering_timeout_wrong_order_and_error_never_confirm(self):
        payload = {'code':'10000','status':'SUCCESS','order_id':'alipay-1','out_biz_no':'order-1'}
        with patch.object(self.payment, 'urlopen', return_value=self.response(payload,tamper=True)):
            self.assertEqual(self.provider.send(self.order).state, 'processing')
        with patch.object(self.payment, 'urlopen', side_effect=TimeoutError):
            self.assertEqual(self.provider.send(self.order).state, 'processing')
        with patch.object(self.provider,'call',return_value={**payload,'out_biz_no':'different'}):
            self.assertEqual(self.provider.send(self.order).state, 'processing')
        with patch.object(self.provider,'call',return_value={'code':'40004','sub_code':'UNKNOWN'}):
            self.assertEqual(self.provider.send(self.order).state, 'processing')

    def test_signed_terminal_failure_and_notification(self):
        with patch.object(self.payment, 'urlopen', return_value=self.response(
                {'code':'10000','status':'FAIL','out_biz_no':'order-1'},'alipay.fund.trans.common.query')):
            self.assertEqual(self.provider.query(self.order).state, 'failed')
        params = dict(app_id='test-app', out_biz_no='order-1', status='SUCCESS')
        params['sign'] = base64.b64encode(self.alipay_key.sign(self.payment.canonical(params).encode(),padding.PKCS1v15(),hashes.SHA256())).decode()
        params['sign_type'] = 'RSA2'
        self.assertTrue(self.provider.verify_notification(params))
        params['status'] = 'FAIL'
        self.assertFalse(self.provider.verify_notification(params))


if __name__ == '__main__':
    unittest.main()
