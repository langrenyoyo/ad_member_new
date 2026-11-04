"""Identity filters for withdrawal and subsidy lists use real enrollments."""
import unittest
from sqlalchemy import select
from . import test_member_policy as fixtures
from app import main_from_txt as m, member_policy as p


class ReviewIdentityTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def test_identity_display_filters_pagination_and_totals(self):
        headers=self.admin_headers()
        with self.factory() as s:
            s.get(m.Member,1).vip=2  # VIP must not affect identity.
            s.add(m.Member(id=3,username='agent',game_id=1,agent_id=1,vip=0,status=1))
            s.flush();p.enrollment(s,s.get(m.Member,3)).level=3
            for cls in (m.Withdrawal,m.Subsidy):
                for rid,uid,status in [(1,1,0),(2,2,1),(3,3,0),(4,3,1),(5,999,0)]:
                    row=cls(id=rid,user_id=uid,game_id=1,agent_id=1,status=status)
                    if cls is m.Withdrawal:row.exchange_value=10
                    else:row.price=10
                    s.add(row)
            s.commit()
        for endpoint in ('withdrawals','subsidies'):
            path='/api/v1/'+endpoint
            for level,ids,label in [(0,{1},'用户'),(1,{2},'团长'),(3,{3,4},'代理')]:
                r=self.client.get(path,headers=headers,params={'member_level':level})
                self.assertEqual(r.status_code,200,r.text)
                data=r.json()
                self.assertEqual(data['total'],len(ids))
                self.assertEqual({x['id'] for x in data['items']},ids)
                self.assertTrue(all(x['member_level']==level and x['member_level_name']==label for x in data['items']))
            for offset in (0,1):
                data=self.client.get(path,headers=headers,params={'member_level':3,'limit':1,'offset':offset}).json()
                self.assertEqual(data['total'],2)
                self.assertEqual(len(data['items']),1)
                self.assertEqual(data['items'][0]['id'],4-offset)
            data=self.client.get(path,headers=headers,params={'member_level':3,'status':0}).json()
            self.assertEqual([x['id'] for x in data['items']],[3])
            if endpoint=='subsidies':
                self.assertEqual(data['summary']['paid'],0)
            else:
                # Withdrawal totals keep their existing status-independent scope.
                self.assertEqual(data['summary']['withdrawn'],10)
            self.assertEqual(data['summary']['pending'],10)
            for invalid in ('2','-1','4','agent'):
                self.assertEqual(self.client.get(path,headers=headers,params={'member_level':invalid}).status_code,422)
            missing=self.client.get(path,headers=headers,params={'user_id':999}).json()['items'][0]
            self.assertIsNone(missing['member_level'])
            self.assertEqual(missing['member_level_name'],'会员不存在')
        with self.factory() as s:
            self.assertIsNone(s.get(p.Enrollment,1))  # Read paths never create enrollments.
            self.assertEqual(s.get(m.Member,1).vip,2)
