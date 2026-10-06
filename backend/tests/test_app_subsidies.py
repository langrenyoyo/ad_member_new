"""APP applications and admin review share records in an isolated database."""
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AppSubsidyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import after discovery so the existing core suite can configure its
        # temporary DATABASE_URL before the application module is loaded.
        global m
        from app import main_from_txt as m

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'test.db'),
                                    connect_args={'check_same_thread': False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.session_patch = patch.object(m, 'SessionLocal', self.factory)
        self.session_patch.start()
        self.image_patch = patch.dict(os.environ, {'MEMBER_IMAGE_DIR': str(Path(self.temp.name) / 'images')})
        self.image_patch.start()
        # No lifespan: test setup must never seed the development database.
        self.client = TestClient(m.app)
        with self.factory() as s:
            s.add_all([m.Agent(id=1, name='Own'), m.Agent(id=2, name='Other'),
                       m.Game(id=1, agent_id=1, name='Game'),
                       m.Game(id=2, agent_id=2, name='Foreign'),
                       m.Game(id=3, agent_id=1, name='Disabled', status=0)])
            user = m.Member(id=1, username='applicant', agent_id=1, game_id=1, coin=50)
            other = m.Member(id=2, username='other', agent_id=1, game_id=1)
            admin = m.AdminUser(username='reviewer', role='reviewer', status=1,
                                password_hash='unused', password_salt='unused')
            s.add_all([user, other, admin])
            s.commit()
            self.auth = {'Authorization': 'Bearer ' + m._create_app_access_token(user)}
            self.other_auth = {'Authorization': 'Bearer ' + m._create_app_access_token(other)}
            self.admin_auth = {'Authorization': 'Bearer ' + m.create_access_token(admin)}
        self.body = {'tx_price': '10.25', 'receive_name': ' Test User ', 'receive_tel': ' contact-001 '}

    def tearDown(self):
        self.client.close()
        self.image_patch.stop()
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def create(self, **changes):
        return self.client.post('/api/app/v1/subsidies', json={**self.body, **changes}, headers=self.auth)

    def test_apply_admin_review_and_app_result(self):
        created = self.create()
        self.assertEqual(created.status_code, 201, created.text)
        row = created.json()['data']
        sid = row['id']
        self.assertEqual((row['user_id'], row['agent_id'], row['game_id']), (1, 1, 1))
        self.assertEqual((row['status'], row['price'], row['tx_price']), (0, 0, 10.25))
        self.assertEqual(row['receive_name'], 'Test User')
        self.assertEqual(row['receive_tel'], 'contact-001')
        self.assertIsNone(row['audited_at'])
        admin_path = f'/api/v1/subsidies/{sid}'
        listing = self.client.get('/api/v1/subsidies', params={'user_id': 1}, headers=self.admin_auth)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.json()['items'][0]['id'], sid)
        edit = self.client.patch(admin_path, json={'price': 5.25}, headers=self.admin_auth)
        self.assertEqual(edit.status_code, 200, edit.text)
        approved = self.client.post(admin_path + '/approve', headers=self.admin_auth)
        self.assertEqual(approved.status_code, 200, approved.text)
        result = self.client.get(f'/api/app/v1/subsidies/{sid}', headers=self.auth).json()['data']
        self.assertEqual((result['status'], result['price']), (1, 5.25))
        self.assertIsNotNone(result['audited_at'])
        self.assertNotIn('audit_operator_id', result)
        self.assertEqual(self.client.post(admin_path + '/approve', headers=self.admin_auth).status_code, 409)
        # Approval is an audit result, not an automatic wallet payout.
        with self.factory() as s:
            self.assertEqual(s.get(m.Member, 1).coin, 50)
            self.assertEqual(s.scalar(select(func.count()).select_from(m.CoinLog)), 0)

    def test_duplicate_reject_and_resubmit(self):
        sid = self.create().json()['data']['id']
        self.assertEqual(self.create().status_code, 409)
        path = f'/api/v1/subsidies/{sid}/reject'
        self.assertEqual(self.client.post(path, json={'message': ' '}, headers=self.admin_auth).status_code, 422)
        rejected = self.client.post(path, json={'message': '请补充凭证'}, headers=self.admin_auth)
        self.assertEqual(rejected.status_code, 200, rejected.text)
        result = self.client.get(f'/api/app/v1/subsidies/{sid}', headers=self.auth).json()['data']
        self.assertEqual((result['status'], result['target_status'], result['sub_msg']), (2, 4, '请补充凭证'))
        self.assertEqual(self.create().status_code, 201)

    def test_ownership_auth_and_no_client_audit(self):
        sid = self.create().json()['data']['id']
        for headers in ({}, self.admin_auth, {'Authorization': 'Bearer invalid'}):
            for method, path in [('get', '/api/app/v1/subsidies'),
                                 ('get', f'/api/app/v1/subsidies/{sid}'),
                                 ('post', '/api/app/v1/subsidies'),
                                 ('post', '/api/app/v1/subsidies/images')]:
                response = getattr(self.client, method)(path, headers=headers)
                self.assertEqual(response.status_code, 401, (method, path, response.text))
        self.assertEqual(self.client.get(f'/api/app/v1/subsidies/{sid}', headers=self.other_auth).status_code, 404)
        self.assertEqual(self.client.get('/api/app/v1/subsidies', headers=self.other_auth).json()['data']['total'], 0)
        self.assertEqual(self.client.get('/api/app/v1/subsidies/999999', headers=self.auth).status_code, 404)
        self.assertEqual(self.client.post(f'/api/v1/subsidies/{sid}/approve', headers=self.auth).status_code, 401)
        with self.factory() as s:
            s.get(m.Member, 1).status = 0
            s.commit()
        self.assertEqual(self.create().status_code, 401)
        self.assertEqual(self.client.get('/api/app/v1/subsidies', headers=self.auth).status_code, 401)

    def test_validation_and_scope(self):
        for changes in [{'tx_price': value} for value in [0, -1, 'NaN', 'Infinity', '1.001', '10000000000', None]] + [
            {'receive_name': ' '}, {'receive_tel': ''}, {'receive_name': 'a' * 65},
            {'price': 999}, {'status': 1}, {'user_id': 2}, {'agent_id': 2}, {'sub_msg': 'approved'},
            {'pics': ['javascript:alert(1)']}, {'pics': ['/api/member-images/' + 'a' * 48 + '.png']},
            {'pics': ['https://example.com/pic.png']}, {'pics': ['x'] * 10}, {'game_id': 0},
        ]:
            with self.subTest(changes=changes):
                response = self.create(**changes)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.create(game_id=2).status_code, 403)
        self.assertEqual(self.create(game_id=3).status_code, 404)
        self.assertEqual(self.create(game_id=999).status_code, 404)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.Subsidy)), 0)
            s.get(m.Agent, 1).status = 0
            s.commit()
        self.assertEqual(self.create().status_code, 403)

    def test_pagination_filtering_and_history_with_disabled_game(self):
        with self.factory() as s:
            s.add_all([m.Subsidy(user_id=1, agent_id=1, game_id=1, status=state) for state in [0, 1, 2]])
            s.add(m.Subsidy(user_id=2, agent_id=1, game_id=1))
            s.get(m.Game, 1).status = 0
            s.commit()
        response = self.client.get('/api/app/v1/subsidies', params={'limit': 1, 'offset': 1}, headers=self.auth)
        data = response.json()['data']
        self.assertEqual((data['total'], len(data['items']), data['items'][0]['status']), (3, 1, 1))
        rejected = self.client.get('/api/app/v1/subsidies', params={'status': 2, 'game_id': 1}, headers=self.auth).json()['data']
        self.assertEqual(rejected['total'], 1)
        self.assertEqual(rejected['items'][0]['status'], 2)
        for params in [{'limit': 0}, {'limit': 101}, {'offset': -1}, {'status': 3}, {'game_id': 0}]:
            self.assertEqual(self.client.get('/api/app/v1/subsidies', params=params, headers=self.auth).status_code, 422)

    def test_concurrent_duplicate_application(self):
        barrier = Barrier(2)
        # Do not enter TestClient's lifespan, which seeds the global engine.
        def isolated_submit():
            client = TestClient(m.app)
            try:
                barrier.wait(timeout=10)
                return client.post('/api/app/v1/subsidies', json=self.body, headers=self.auth).status_code
            finally:
                client.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: isolated_submit(), range(2)))
        self.assertEqual(sorted(outcomes), [201, 409])
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.Subsidy)), 1)

    def test_image_upload_and_admin_gallery_compatibility(self):
        image = BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(image, format='PNG')
        upload = self.client.post('/api/app/v1/subsidies/images', content=image.getvalue(), headers=self.auth)
        self.assertEqual(upload.status_code, 201, upload.text)
        url = upload.json()['data']['url']
        self.assertEqual(self.client.get(url).status_code, 200)
        created = self.create(pics=[url])
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['data']['pics'], url)
        admin = self.client.get('/api/v1/subsidies', headers=self.admin_auth).json()['items'][0]
        self.assertEqual(admin['pics'], url)
        self.assertEqual(self.client.post('/api/app/v1/subsidies/images', content=b'not an image', headers=self.auth).status_code, 422)
        self.assertEqual(self.client.post('/api/app/v1/subsidies/images', content=b'x' * (m.MAX_UPLOAD_BYTES + 1), headers=self.auth).status_code, 413)

    def campaign_setup(self, quota=50):
        from datetime import UTC, datetime
        fixed = datetime(2026, 10, 6, 5, 0, tzinfo=UTC)
        self.clock_patch = patch.object(m, 'now', return_value=fixed)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        with self.factory() as s:
            admin = s.scalar(select(m.AdminUser))
            admin.role = 'superadmin'
            campaign = m.subsidy_campaigns.SubsidyCampaign(game_id=1, title='Recharge subsidy', enabled=1, daily_quota=quota)
            s.add(campaign)
            s.add_all([m.Withdrawal(user_id=uid, agent_id=1, game_id=1, exchange_value=5,
                status=1, plan_status=1, transferred_at=fixed) for uid in (1, 2)])
            s.commit()
            cid = campaign.id
        urls = []
        for color in ['red', 'green', 'blue']:
            image = BytesIO()
            Image.new('RGB', (2, 2), color).save(image, format='PNG')
            urls.append(self.client.post('/api/app/v1/subsidies/images', content=image.getvalue(), headers=self.auth).json()['data']['url'])
        self.campaign_body = dict(request_key='test-request-001', download_image=urls[0], install_image=urls[1],
                                  recharge_image=urls[2], receive_name='User', receive_tel='Contact')
        return cid

    def test_campaign_apply_snapshot_review_and_replay(self):
        from datetime import timedelta
        cid = self.campaign_setup()
        path = f'/api/app/v1/subsidy-campaigns/{cid}'
        info = self.client.get(path, headers=self.auth).json()['data']
        self.assertEqual((info['remaining'], info['confirmed_withdrawal_cents'], info['eligible']), (50, 500, True))
        response = self.client.post(path+'/applications', json=self.campaign_body, headers=self.auth)
        self.assertEqual(response.status_code, 201, response.text)
        row = response.json()['data']
        self.assertEqual((row['tx_price'], row['price']), (5, 12))
        self.assertEqual(row['campaign']['evidence']['recharge_image'], self.campaign_body['recharge_image'])
        self.assertFalse(row['campaign']['overdue'])
        sid = row['id']
        self.assertEqual(self.client.post(path+'/applications', json=self.campaign_body, headers=self.auth).json()['data']['id'], sid)
        changed = {**self.campaign_body, 'receive_name': 'Changed'}
        self.assertEqual(self.client.post(path+'/applications', json=changed, headers=self.auth).status_code, 409)
        self.assertEqual(self.create().status_code, 409)  # no legacy endpoint bypass
        admin_row = self.client.get(f'/api/v1/subsidies/{sid}', headers=self.admin_auth).json()
        self.assertEqual(admin_row['campaign']['reward_cents'], 1200)
        with self.factory() as s:
            s.get(m.subsidy_campaigns.SubsidyCampaign, cid).reward_cents = 2400
            reservation = s.scalar(select(m.subsidy_campaigns.SubsidyReservation))
            reservation.review_due_at = m.now() - timedelta(hours=1)
            s.commit()
        detail = self.client.get(f'/api/app/v1/subsidies/{sid}', headers=self.auth).json()['data']
        self.assertEqual(detail['campaign']['reward_cents'], 1200)
        self.assertTrue(detail['campaign']['overdue'])
        self.assertEqual(self.client.post(f'/api/v1/subsidies/{sid}/reject', json={'message':'invalid receipt'}, headers=self.admin_auth).status_code, 200)
        fresh = {**self.campaign_body, 'request_key': 'test-request-002'}
        self.assertEqual(self.client.post(path+'/applications', json=fresh, headers=self.auth).status_code, 409)
        self.assertEqual(self.client.delete(f'/api/v1/subsidies/{sid}', headers=self.admin_auth).status_code, 204)
        info = self.client.get(path, headers=self.auth).json()['data']
        self.assertEqual((info['used'], info['remaining']), (1, 49))
        self.assertEqual(self.client.post(path+'/applications', json=self.campaign_body, headers=self.auth).status_code, 410)

    def test_campaign_last_slot_concurrency(self):
        cid = self.campaign_setup(quota=1)
        barrier = Barrier(2)
        path = f'/api/app/v1/subsidy-campaigns/{cid}/applications'
        def submit(auth):
            client = TestClient(m.app)
            try:
                barrier.wait(timeout=10)
                return client.post(path, json=self.campaign_body, headers=auth).status_code
            finally:
                client.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(submit, [self.auth, self.other_auth]))
        self.assertEqual(sorted(outcomes), [201, 409])
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.subsidy_campaigns.SubsidyReservation)), 1)

    def test_campaign_beijing_day_and_confirmed_eligibility(self):
        from datetime import timedelta
        cid = self.campaign_setup()
        _, start, end = m.subsidy_campaigns.day_bounds()
        with self.factory() as s:
            s.query(m.Withdrawal).delete()
            s.add_all([
                m.Withdrawal(user_id=1, agent_id=1, game_id=1, exchange_value=3, status=1, plan_status=1, transferred_at=start),
                m.Withdrawal(user_id=1, agent_id=1, game_id=1, exchange_value=10, status=1, plan_status=1, transferred_at=start-timedelta(seconds=1)),
                m.Withdrawal(user_id=1, agent_id=1, game_id=1, exchange_value=10, status=1, plan_status=1, transferred_at=end),
                m.Withdrawal(user_id=1, agent_id=1, game_id=1, exchange_value=10, status=1, plan_status=0, transferred_at=m.now()),
                m.Withdrawal(user_id=2, agent_id=1, game_id=1, exchange_value=10, status=1, plan_status=1, transferred_at=m.now()),
            ])
            s.commit()
        path = f'/api/app/v1/subsidy-campaigns/{cid}'
        info = self.client.get(path, headers=self.auth).json()['data']
        self.assertEqual(info['confirmed_withdrawal_cents'], 300)
        self.assertFalse(info['eligible'])
        self.assertEqual(self.client.post(path+'/applications', json=self.campaign_body, headers=self.auth).status_code, 409)
        with self.factory() as s:
            s.add(m.Withdrawal(user_id=1, agent_id=1, game_id=1, exchange_value=2, status=1, plan_status=1, transferred_at=m.now()))
            s.commit()
        self.assertEqual(self.client.post(path+'/applications', json=self.campaign_body, headers=self.auth).status_code, 201)
        m.now.return_value = end + timedelta(seconds=1)
        info = self.client.get(path, headers=self.auth).json()['data']
        self.assertEqual((info['used'], info['remaining'], info['confirmed_withdrawal_cents']), (0, 50, 1000))

    def test_campaign_config_permissions_scope_and_evidence(self):
        cid = self.campaign_setup()
        path = f'/api/app/v1/subsidy-campaigns/{cid}/applications'
        for fields in [{'download_image': ''}, {'install_image': self.campaign_body['download_image']},
                       {'recharge_image': 'https://example.com/receipt.png'}, {'price': 1000}]:
            response = self.client.post(path, json={**self.campaign_body, **fields}, headers=self.auth)
            self.assertEqual(response.status_code, 422, response.text)
        config = dict(game_id=1, title='Configured', enabled=1, daily_quota=50,
            withdrawal_cents=500, recharge_cents=600, reward_cents=1200, review_hours=24, instructions='Check receipts')
        admin_path = '/api/v1/subsidy-campaigns'
        self.assertEqual(self.client.post(admin_path, json=config, headers=self.auth).status_code, 401)
        with self.factory() as s:
            s.scalar(select(m.AdminUser)).role = 'reviewer'
            s.commit()
        self.assertEqual(self.client.put(admin_path+f'/{cid}', json=config, headers=self.admin_auth).status_code, 403)
        with self.factory() as s:
            s.scalar(select(m.AdminUser)).role = 'superadmin'
            s.commit()
        self.assertEqual(self.client.put(admin_path+f'/{cid}', json={**config, 'daily_quota': 0}, headers=self.admin_auth).status_code, 422)
        self.assertEqual(self.client.put(admin_path+f'/{cid}', json={**config, 'game_id': 2}, headers=self.admin_auth).status_code, 422)
        self.assertEqual(self.client.put(admin_path+f'/{cid}', json={**config, 'enabled': 0}, headers=self.admin_auth).status_code, 200)
        self.assertEqual(self.client.post(path, json=self.campaign_body, headers=self.auth).status_code, 409)
        self.assertEqual(self.client.get('/api/app/v1/subsidy-campaigns', headers=self.auth).json()['data']['total'], 0)
        with self.factory() as s:
            s.get(m.Member, 1).agent_id = 2
            s.commit()
        self.assertEqual(self.client.get(f'/api/app/v1/subsidy-campaigns/{cid}', headers=self.auth).status_code, 404)


if __name__ == '__main__':
    unittest.main()
