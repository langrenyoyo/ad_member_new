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
        self.assertEqual(self.submit('owner').status_code, 204)
        response = self.client.put('/api/app/v1/me/alipay', headers=self.auth,
            json={'account': '13000000000', 'real_name': 'Test Member', 'current_password': 'NewPassword123'})
        self.assertEqual(response.status_code, 200, response.text)

    def test_other_wechat_cannot_reset_password(self):
        self.assertEqual(self.submit('someone-else').status_code, 403)
        with self.factory() as session:
            user = session.get(m.Member, 1)
            self.assertTrue(m.verify_password('OldPassword123', user.password_hash, user.password_salt))

    def test_missing_login_and_weak_password_rejected(self):
        response = self.client.post('/api/app/v1/auth/wechat-password',
            json={'code': 'fresh-code', 'new_password': 'NewPassword123'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.submit('owner', '12345678').status_code, 422)

    def test_other_app_identity_cannot_reset_password(self):
        with self.factory() as session:
            linked = session.query(m.WechatIdentity).one()
            linked.app_id = 'another-app'
            session.commit()
        self.assertEqual(self.submit('owner').status_code, 403)


if __name__ == '__main__':
    unittest.main()
