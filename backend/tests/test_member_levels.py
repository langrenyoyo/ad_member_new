"""Membership identities in admin editing, separate from legacy VIP."""
import unittest
from sqlalchemy import select
from . import test_member_policy as fixtures
from app import main_from_txt as m, member_policy as p


class MemberLevelTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def test_list_filter_pagination_and_missing_enrollment(self):
        headers = self.admin_headers()
        with self.factory() as session:
            for mid, level, game_id in [(3, 3, 1), (4, 0, 1), (5, 1, 1), (6, 3, 2)]:
                member = m.Member(id=mid, username=f'member-{mid}', agent_id=1, game_id=game_id, status=1)
                session.add(member); session.flush()
                p.enrollment(session, member).level = level
            session.add(m.Game(id=2, agent_id=1, name='Other'))
            session.commit()
        for level, ids in [(0, {1, 4}), (1, {2, 5}), (3, {3})]:
            response = self.client.get(f'/api/v1/members?member_level={level}&game_id=1', headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data['total'], len(ids))
            self.assertEqual({row['id'] for row in data['items']}, ids)
            self.assertTrue(all(row['member_level'] == level for row in data['items']))
        first = self.client.get('/api/v1/members?member_level=1&limit=1&offset=0', headers=headers).json()
        second = self.client.get('/api/v1/members?member_level=1&limit=1&offset=1', headers=headers).json()
        self.assertEqual(first['total'], 2)
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        self.assertTrue(first['permissions']['member_level'])
        for invalid in ('2', '-1', 'abc'):
            self.assertEqual(self.client.get('/api/v1/members?member_level='+invalid, headers=headers).status_code, 422)

    def test_atomic_member_edit_and_legacy_endpoint_share_identity(self):
        headers = self.admin_headers(); path = '/api/v1/members/1'
        self.assertEqual(self.client.get(path, headers=headers).json()['member_level'], 0)
        for level in (1, 3, 0):
            response = self.client.patch(path, headers=headers, json={'member_level': level, 'name': 'Changed', 'vip': 2})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['member_level'], level)
            self.assertEqual(response.json()['vip'], 2)
            detail = self.client.get(path, headers=headers).json()
            self.assertEqual(detail['member_level_name'], p.MEMBER_LEVEL_NAMES[level])
            with self.factory() as session:
                self.assertEqual(session.get(p.Enrollment, 1).level, level)
                self.assertEqual(session.get(m.Member, 1).parent_id, 0)
                self.assertEqual(session.get(m.Member, 1).coin, 0)
        response = self.client.put(path+'/level', headers=headers, json={'level': 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(path, headers=headers).json()['member_level'], 3)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(m.func.count()).select_from(m.AdminOperation)), 4)

    def test_invalid_or_unauthorized_change_does_not_partially_save_profile(self):
        headers = self.admin_headers(); path = '/api/v1/members/1'
        for body in ({'member_level':2}, {'member_level':None}, {'member_level':1,'coin':99},
                     {'member_level':3,'whitelist_min_coin':10}):
            response = self.client.patch(path, headers=headers, json={**body,'name':'Should not save'})
            self.assertIn(response.status_code, (409,422), response.text)
        with self.factory() as session:
            for role in ('operator','risk'):
                admin=m.AdminUser(username=role,password_hash='x',password_salt='x',role=role,status=1)
                session.add(admin); session.flush()
            session.commit()
        for role in ('operator','risk'):
            with self.factory() as session:
                admin=session.scalar(select(m.AdminUser).where(m.AdminUser.username==role))
                role_headers={'Authorization':'Bearer '+m.create_access_token(admin)}
            self.assertFalse(self.client.get(path, headers=role_headers).json()['can_edit_member_level'])
            response=self.client.patch(path,headers=role_headers,json={'member_level':3,'name':'Should not save'})
            self.assertEqual(response.status_code,403,response.text)
        with self.factory() as session:
            self.assertIsNone(session.get(p.Enrollment,1))
            self.assertNotEqual(session.get(m.Member,1).name,'Should not save')
            self.assertEqual(session.scalar(select(m.func.count()).select_from(m.AdminOperation)),0)

    def test_role_edit_changes_invitation_eligibility(self):
        headers=self.admin_headers()
        for level in (0,1,3):
            self.assertEqual(self.client.patch('/api/v1/members/2',headers=headers,json={'member_level':level}).status_code,200)
            with self.factory() as session:
                user=session.get(m.Member,1);code=session.get(p.Enrollment,2).invite_code
                if level==0:
                    with self.assertRaises(m.HTTPException):p.bind_registration(session,user,code)
                else:
                    p.bind_registration(session,user,code)
                    self.assertEqual(user.parent_id,2)
