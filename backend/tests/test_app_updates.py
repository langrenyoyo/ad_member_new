import unittest
from sqlalchemy import select
import test_member_policy as fixtures
from app import main_from_txt as m


class UpdateTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def test_policy_modes_permissions_and_validation(self):
        path='/api/v1/games/1/app-update'
        public='/api/app/v1/app-update?game_id=1'
        self.assertFalse(self.client.get(public).json()['enabled'])
        body=dict(enabled=True,force_update=True,package_name='com.example.app',
                  version_code=16,version_name='1.0.15',download_url='https://example.com/app.apk',notes='Update')
        self.assertIn(self.client.put(path,json=body).status_code,(401,403))
        headers=self.admin_headers()
        self.assertEqual(self.client.put(path,json=body,headers=headers).status_code,200)
        response=self.client.get(public)
        self.assertEqual(response.json(),body)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(self.client.put(path,json={**body,'download_url':'http://example.com/a'},headers=headers).status_code,422)
        body['force_update']=False
        self.assertEqual(self.client.put(path,json=body,headers=headers).status_code,200)
        self.assertFalse(self.client.get(public).json()['force_update'])
        self.assertEqual(self.client.get('/api/app/v1/app-update?game_id=9999').status_code,404)
