"""Fresh WeChat authorization is required to set a member password."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import main_from_txt as m


class WechatPasswordTests(unittest.TestCase):
    def test_migration_marks_legacy_oauth_accounts_without_changing_hashes(self):
        import importlib.util
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import text
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/e941_system_password.py'
        spec = importlib.util.spec_from_file_location('password_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE members (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)'))
                connection.execute(text('CREATE TABLE wechat_identities (member_id INTEGER)'))
                connection.execute(text("INSERT INTO members VALUES (1, 'wx_legacy', 'old-hash'), (2, 'phone-user', 'phone-hash')"))
                connection.execute(text('INSERT INTO wechat_identities VALUES (1)'))
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                self.assertEqual(connection.execute(text('SELECT system_password_set, password_hash FROM members ORDER BY id')).all(),
                                 [(0, 'old-hash'), (1, 'phone-hash')])
        finally:
            engine.dispose()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'test.db'),
                                    connect_args={'check_same_thread': False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patcher = patch.object(m, 'SessionLocal', self.factory)
        self.patcher.start()
        self.client = TestClient(m.app)
        with self.factory() as session:
            hashed, salt = m.hash_password('OldPassword123')
            user = m.Member(id=1, username='wx_test', game_id=1, agent_id=1,
                            password_hash=hashed, password_salt=salt, status=1)
            session.add_all([m.Agent(id=1, name='Agent'),
                m.Game(id=1, agent_id=1, name='Game', wx_appid='test-app', wx_secert='test-secret'), user,
                m.WechatIdentity(member_id=1, provider='app', app_id='test-app', openid='owner', unionid='')])
            session.commit()
            self.auth = {'Authorization': 'Bearer ' + m._create_app_access_token(user)}

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def submit(self, openid, password='NewPassword123'):
        with patch.object(m, '_wechat_exchange_code', return_value={'openid': openid, 'unionid': ''}) as exchange:
            response = self.client.post('/api/app/v1/auth/wechat-password', headers=self.auth,
                                        json={'code': 'fresh-code', 'new_password': password})
            if response.status_code == 204:
                exchange.assert_called_once_with('app', 'fresh-code', 'test-app', 'test-secret')
            return response

    def test_owner_can_set_password_and_bind_alipay(self):
        with self.factory() as session:
            session.get(m.Member, 1).system_password_set = False
            session.commit()
        before = self.client.get('/api/app/v1/onboarding', headers=self.auth)
        self.assertTrue(before.json()['data']['system_password_required'])
        self.assertEqual(self.submit('owner').status_code, 204)
        after = self.client.get('/api/app/v1/onboarding', headers=self.auth)
        self.assertFalse(after.json()['data']['system_password_required'])
        response = self.client.put('/api/app/v1/me/alipay', headers=self.auth,
            json={'account': '13000000000', 'real_name': 'Test Member', 'current_password': 'NewPassword123'})
        self.assertEqual(response.status_code, 200, response.text)

    def test_registration_invite_does_not_gate_existing_wechat_relogin(self):
        import json
        from app import member_policy as p
        with self.factory() as session:
            session.get(m.Game, 1).settings_json = json.dumps({'member_policy': {
                'require_registration_invite': True, 'require_invite': False, 'require_usage': False}})
            parent = m.Member(id=2, username='invite-parent', game_id=1, agent_id=1, status=1)
            session.add(parent)
            session.flush()
            enrollment = p.enrollment(session, parent)
            enrollment.level = 1
            code = enrollment.invite_code
            session.commit()
        body = {'provider': 'app', 'code': 'fresh-code', 'game_id': 1, 'device_id': 'test-device'}
        with patch.object(m, '_wechat_exchange_code', return_value={'openid': 'owner', 'unionid': ''}):
            for _ in range(2):
                result = self.client.post('/api/app/v1/auth/wechat', json=body)
                self.assertEqual(result.status_code, 200, result.text)
                headers = {'Authorization': 'Bearer ' + result.json()['data']['access_token']}
                onboarding = self.client.get('/api/app/v1/onboarding', headers=headers)
                self.assertEqual(onboarding.status_code, 200, onboarding.text)
                self.assertFalse(onboarding.json()['data']['policy']['require_invite'])
                self.assertEqual(onboarding.json()['data']['parent_id'], 0)
                self.assertEqual(self.client.post('/api/app/v1/auth/logout', headers=headers, json={}).status_code, 204)
        with patch.object(m, '_wechat_exchange_code', return_value={'openid': 'new-owner', 'unionid': ''}):
            self.assertEqual(self.client.post('/api/app/v1/auth/wechat', json=body).status_code, 422)
            with self.factory() as session:
                self.assertIsNone(session.query(m.WechatIdentity).filter_by(openid='new-owner').first())
            result = self.client.post('/api/app/v1/auth/wechat', json={**body, 'invite_code': code})
            self.assertEqual(result.status_code, 200, result.text)
        with self.factory() as session:
            identity = session.query(m.WechatIdentity).filter_by(openid='new-owner').one()
            self.assertEqual(session.get(m.Member, identity.member_id).parent_id, 2)
            self.assertEqual(session.get(m.Member, 1).parent_id, 0)

    def test_login_risk_denial_is_persisted_for_existing_and_new_members(self):
        import json
        with self.factory() as session:
            session.get(m.Game,1).settings_json=json.dumps({'member_policy':{
                'block_signals':['root'], 'require_registration_invite':False}})
            session.commit()
        for openid in ('owner','new-blocked-owner'):
            with patch.object(m,'_wechat_exchange_code',return_value={'openid':openid,'unionid':''}):
                result=self.client.post('/api/app/v1/auth/wechat',headers={'X-Device-Risk':'root,developer'},json={
                    'provider':'app','code':'fresh-code','game_id':1,'device_id':'private-device-id'})
            self.assertEqual(result.status_code,403,result.text)
        with self.factory() as session:
            records=session.query(m.AdFlowLog).filter_by(event_type='device_blocked').order_by(m.AdFlowLog.id).all()
            self.assertEqual(len(records),2)
            self.assertEqual([r.member_id for r in records],[1,0])
            for record in records:
                detail=json.loads(record.detail_json)
                self.assertEqual(detail['signals'],['root'])
                self.assertEqual(detail['stage'],'login')
                self.assertNotIn('private-device-id',record.detail_json)
            self.assertIsNone(session.query(m.WechatIdentity).filter_by(openid='new-blocked-owner').first())

    def test_other_wechat_cannot_reset_password(self):
        with self.factory() as session:
            session.get(m.Member, 1).system_password_set = False
            session.commit()
        self.assertEqual(self.submit('someone-else').status_code, 403)
        with self.factory() as session:
            user = session.get(m.Member, 1)
            self.assertFalse(user.system_password_set)
            self.assertTrue(m.verify_password('OldPassword123', user.password_hash, user.password_salt))

    def test_missing_login_and_weak_password_rejected(self):
        response = self.client.post('/api/app/v1/auth/wechat-password',
            json={'code': 'fresh-code', 'new_password': 'NewPassword123'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.submit('owner', '12345').status_code, 422)

    def test_other_app_identity_cannot_reset_password(self):
        with self.factory() as session:
            linked = session.query(m.WechatIdentity).one()
            linked.app_id = 'another-app'
            session.commit()
        self.assertEqual(self.submit('owner').status_code, 403)

    def test_new_wechat_account_requires_password_setup(self):
        import json
        with self.factory() as session:
            session.get(m.Game, 1).settings_json = json.dumps({'member_policy': {'require_registration_invite': False}})
            session.commit()
        with patch.object(m, '_wechat_exchange_code', return_value={'openid': 'new-owner', 'unionid': ''}):
            result = self.client.post('/api/app/v1/auth/wechat', json={
                'provider': 'app', 'code': 'fresh-code', 'game_id': 1, 'device_id': 'test-device'})
        self.assertEqual(result.status_code, 200, result.text)
        with self.factory() as session:
            identity = session.query(m.WechatIdentity).filter_by(openid='new-owner').one()
            self.assertFalse(session.get(m.Member, identity.member_id).system_password_set)


if __name__ == '__main__':
    unittest.main()
