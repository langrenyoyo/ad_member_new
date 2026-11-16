"""Browser invitation validation and SMS registration on disposable databases."""
import json
import os
import unittest
from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import select
from . import test_member_policy as fixtures
from app import main_from_txt as m, member_policy as p, sms_auth as sms


class InviteLandingTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown

    def code(self, uid=2):
        with self.factory() as s:
            return p.enrollment(s, s.get(m.Member, uid)).invite_code

    def resolve(self, code=None, game=1):
        return self.client.get('/api/app/v1/invitations/resolve', params={
            'game_id': game, 'invite_code': code or self.code()})

    def test_all_members_have_browser_links_but_only_leaders_and_agents_are_eligible(self):
        for level in (0, 1, 3):
            with self.factory() as s:
                s.get(p.Enrollment, 2).level = level
                s.commit()
            data = self.resolve(self.code().lower()).json()['data']
            self.assertEqual(data['registration_eligible'], level in (1, 3))
            self.assertEqual(data['invite_path'], '/invite.html?game_id=1&invite_code=' + self.code())
            self.assertNotIn('phone', data)
            self.assertNotIn('member_id', data)
        data = self.client.get('/api/app/v1/invite-code', headers=self.auth).json()['data']
        self.assertEqual(len(data['invite_code']), 6)
        self.assertIn('/invite.html?', data['invite_path'])
        self.assertFalse(data['registration_eligible'])

    def test_inactive_owner_wrong_game_invalid_code_are_rejected(self):
        self.assertEqual(self.resolve('bad!xx').status_code, 422)
        self.assertEqual(self.resolve('ZZ9999').status_code, 404)
        with self.factory() as s:
            s.add(m.Game(id=2, agent_id=1, name='other', status=1))
            s.commit()
        self.assertEqual(self.resolve(game=2).status_code, 404)
        with self.factory() as s:
            s.get(m.Member, 2).status = 0
            s.commit()
        self.assertEqual(self.resolve().status_code, 404)

    def test_download_configuration_is_validated_and_not_fabricated(self):
        for value, expected in [('https://example.com/app.apk', 'https://example.com/app.apk'),
            ('/downloads/app.apk', '/downloads/app.apk'), ('javascript:alert(1)', None),
            ('//evil.example/app.apk', None), ('https://u:p@example.com/app.apk', None)]:
            with patch.dict(os.environ, {'APP_DOWNLOAD_URL': value}):
                self.assertEqual(self.resolve().json()['data']['download_url'], expected)

    def test_app_link_uses_deployment_scheme_and_rejects_unexpected_schemes(self):
        for value, expected in [('hehe', 'hehe'), ('guangjiyexing', 'guangjiyexing'),
                                ('javascript', 'yazhiyiji')]:
            with patch.dict(os.environ, {'APP_INVITE_SCHEME': value}):
                self.assertEqual(self.resolve().json()['data']['app_open_url'],
                                 expected + '://invite?game_id=1&invite_code=' + self.code())

    def test_browser_sms_auto_registration_binds_verified_invite_and_rejects_replay(self):
        phone, challenge, code = '13900001111', 'browser-test', '123456'
        with self.factory() as s:
            s.add(sms.SmsCode(id=challenge, phone_hash=sms.digest(phone), ip_hash='ip', game_id=1,
                code_hash=sms.digest(challenge + code), expires_at=m.now()+timedelta(minutes=5), state='ready'))
            s.commit()
        body = {'phone': phone, 'game_id': 1, 'challenge_id': challenge, 'code': code,
            'device_id': 'web-test-device', 'platform': 'web', 'invite_code': self.code()}
        response = self.client.post('/api/app/v1/auth/sms/login', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        with self.factory() as s:
            member = s.scalar(select(m.Member).where(m.Member.username == phone))
            self.assertEqual(member.parent_id, 2)
            self.assertEqual(s.get(p.Enrollment, member.id).parent_id, 2)
        self.assertNotIn('access_token', self.resolve().text)
        self.assertEqual(self.client.post('/api/app/v1/auth/sms/login', json=body).status_code, 401)

    def test_static_landing_is_public_and_has_no_backend_secret(self):
        for path in ('/invite.html', '/invite.js', '/invite.css'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('JWT_SECRET', response.text)
        script = self.client.get('/invite.js').text
        self.assertNotIn('localStorage', script)
        self.assertNotIn('setItem("access', script)


if __name__ == '__main__':
    unittest.main()
