"""Registration policy checks against isolated databases, never live accounts."""
import json
from datetime import timedelta
from unittest.mock import patch
import unittest

from . import test_member_policy as fixtures
from app import main_from_txt as m, member_policy as p, sms_auth as sms
from sqlalchemy import select


class RegistrationInviteTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def exercise(self, channel):
        cases = [
            (True, '', 1, 422), (True, '   ', 1, 422),
            (True, 'bad-code', 1, 422), (True, 'parent', 0, 422),
            (True, 'parent', 1, 200), (True, 'parent', 3, 200),
            (False, '', 1, 200), (False, '   ', 1, 200),
            (False, 'bad-code', 1, 422), (False, 'parent', 0, 422),
            (False, 'parent', 1, 200), (False, 'parent', 3, 200),
        ]
        for index, (required, code, level, expected) in enumerate(cases):
            with self.subTest(channel=channel, required=required, code=code, level=level):
                username = f'1380000{index:04d}'
                challenge = f'challenge-{index}'
                with self.factory() as session:
                    game = session.get(m.Game, 1)
                    game.settings_json = json.dumps({'member_policy': {'require_registration_invite': required}})
                    game.wx_appid = 'test-app'
                    game.wx_secert = 'test-secret'
                    parent = session.get(p.Enrollment, 2)
                    parent.level = level
                    actual_code = parent.invite_code.lower() if code == 'parent' else code
                    if channel == 'sms':
                        session.add(sms.SmsCode(id=challenge, phone_hash=sms.digest(username), ip_hash='ip',
                            game_id=1, code_hash=sms.digest(challenge + '123456'),
                            expires_at=m.now() + timedelta(minutes=5), state='ready'))
                    session.commit()
                    before = session.scalar(select(m.func.count()).select_from(m.Member))
                body = {'game_id': 1, 'device_id': f'device-{index}', 'invite_code': actual_code}
                if channel == 'password':
                    response = self.client.post('/api/app/v1/auth/register', json={**body,
                        'username': username, 'password': 'Password123'})
                elif channel == 'sms':
                    response = self.client.post('/api/app/v1/auth/sms/login', json={**body,
                        'phone': username, 'challenge_id': challenge, 'code': '123456'})
                else:
                    with patch.object(m, '_wechat_exchange_code', return_value={'openid': username, 'unionid': ''}):
                        response = self.client.post('/api/app/v1/auth/wechat-login', json={**body,
                            'code': 'fresh-code', 'provider': 'app'})
                expected_status = 201 if channel == 'password' and expected == 200 else expected
                self.assertEqual(response.status_code, expected_status, response.text)
                with self.factory() as session:
                    after = session.scalar(select(m.func.count()).select_from(m.Member))
                    self.assertEqual(after, before + (expected == 200))
                    if expected == 200:
                        member = session.scalar(select(m.Member).order_by(m.Member.id.desc()).limit(1))
                        parent_id = 2 if code == 'parent' else 0
                        self.assertEqual(member.parent_id, parent_id)
                        self.assertEqual(session.get(p.Enrollment, member.id).parent_id, parent_id)

    def test_password_registration_switch(self):
        self.exercise('password')

    def test_sms_registration_switch(self):
        self.exercise('sms')

    def test_wechat_registration_switch(self):
        self.exercise('wechat')

    def test_default_and_saved_switch_are_public_and_scoped_to_game(self):
        self.assertTrue(self.client.get('/api/app/v1/policy?game_id=1').json()['data']['require_registration_invite'])
        headers = self.admin_headers()
        path = '/api/v1/games/1/member-policy'
        with self.factory() as session:
            session.add(m.Game(id=2, agent_id=1, name='Other game'))
            session.commit()
        for required in (False, True):
            body = self.client.get(path, headers=headers).json()
            body['require_registration_invite'] = required
            response = self.client.put(path, headers=headers, json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.client.get(path, headers=headers).json()['require_registration_invite'], required)
            self.assertEqual(self.client.get('/api/app/v1/policy?game_id=1').json()['data']['require_registration_invite'], required)
            self.assertTrue(self.client.get('/api/app/v1/policy?game_id=2').json()['data']['require_registration_invite'])
        self.assertEqual(self.client.put(path, headers=self.auth, json={'require_registration_invite': False}).status_code, 401)

    def test_disabled_switch_still_rejects_inactive_and_other_game_parent(self):
        with self.factory() as session:
            game = session.get(m.Game, 1)
            game.settings_json = json.dumps({'member_policy': {'require_registration_invite': False}})
            user, owner = session.get(m.Member, 1), session.get(m.Member, 2)
            code = session.get(p.Enrollment, 2).invite_code
            for status, game_id in [(0, 1), (1, 2)]:
                owner.status, owner.game_id = status, game_id
                session.flush()
                with self.assertRaises(m.HTTPException):
                    p.bind_registration(session, user, code)
                self.assertFalse(user.parent_id)

    def test_switch_can_be_saved_during_ecpm_key_outage(self):
        fixtures.MemberPolicyTests.policy(self, reward_enabled=True, reward_basis='verified_cny_ecpm')
        headers = self.admin_headers()
        path = '/api/v1/games/1/member-policy'
        body = self.client.get(path, headers=headers).json()
        body['require_registration_invite'] = False
        with patch.object(p, 'check_reward_configuration', side_effect=RuntimeError('key unavailable')) as check:
            response = self.client.put(path, headers=headers, json=body)
            self.assertEqual(response.status_code, 200, response.text)
            check.assert_not_called()
