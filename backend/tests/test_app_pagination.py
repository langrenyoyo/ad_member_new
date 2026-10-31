"""APP page parameters slice real queries without changing member scope."""
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import main_from_txt as m


class AppPaginationTests(unittest.TestCase):
    paths = ('ads/history', 'wallet/coin-logs', 'withdrawals', 'subsidies',
             'commissions', 'commission-team', 'subsidy-campaigns')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///'+str(Path(self.temp.name)/'test.db'),
                                    connect_args={'check_same_thread': False})
        m.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine)
        self.patcher = patch.object(m, 'SessionLocal', self.factory)
        self.patcher.start()
        self.client = TestClient(m.app)
        with self.factory() as s:
            for uid in (1, 2):
                s.add(m.Agent(id=uid, name='agent', status=1))
                s.add(m.Game(id=uid, agent_id=uid, name='game', status=1))
                user = m.Member(id=uid, username='user-'+str(uid), game_id=uid, agent_id=uid)
                s.add(user)
                s.flush()
                if uid == 1:
                    self.headers = {'Authorization': 'Bearer '+m._create_app_access_token(user)}
                for i in range(5):
                    sid = f'ads-{uid}-{i}'
                    s.add(m.AppAdSession(id=sid, member_id=uid, game_id=uid, agent_id=uid,
                        request_id='req-'+sid, session_token_hash='test',
                        expires_at=m.now()+timedelta(minutes=5), created_at=m.now().replace(microsecond=0)))
                    s.add(m.CoinLog(user_id=uid, game_id=uid, coin=1,
                                    created_at=m.now().replace(microsecond=0)))
                    s.add(m.Withdrawal(user_id=uid, game_id=uid, agent_id=uid))
                    s.add(m.Subsidy(user_id=uid, game_id=uid, agent_id=uid, status=i % 2))
                    s.add(m.member_policy.RewardLedger(ad_session_id=sid, member_id=uid,
                        beneficiary_id=uid, game_id=uid, kind='commission_1', amount=1, rule_json='{}'))
                    child = m.Member(id=100*uid+i, username=f'child-{uid}-{i}', game_id=uid, agent_id=uid)
                    s.add(child)
                    s.add(m.member_policy.Enrollment(member_id=child.id, parent_id=uid,
                        invite_code=f'INV-{uid}-{i}', level=0))
                    s.add(m.subsidy_campaigns.SubsidyCampaign(game_id=uid, title='campaign', enabled=1))
            s.commit()

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def get(self, path, **params):
        response = self.client.get('/api/app/v1/'+path, params=params, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['data']

    def test_all_record_pages_are_scoped_stable_and_backward_compatible(self):
        for path in self.paths:
            with self.subTest(path=path):
                all_rows = self.get(path)
                self.assertEqual(all_rows['total'], 5)
                ids = [x['id'] for x in all_rows['items']]
                first = self.get(path, page=1, page_size=2)
                second = self.get(path, page=2, page_size=2)
                last = self.get(path, page=3, page_size=2)
                self.assertEqual([x['id'] for p in (first, second, last) for x in p['items']], ids)
                self.assertEqual((second['page'], second['page_size'], second['total_pages'],
                                  second['offset'], second['limit'], second['has_more']), (2,2,3,2,2,True))
                self.assertFalse(last['has_more'])
                empty = self.get(path, page=4, page_size=2)
                self.assertEqual(empty['items'], [])
                self.assertEqual(empty['total'], 5)
                self.assertEqual(empty['page'], 4)
                self.assertFalse(empty['has_more'])
                self.assertEqual(self.get(path, limit=2, offset=2)['items'], second['items'])
                self.assertEqual(self.get(path, page=2, limit=2)['items'], second['items'])
                self.assertEqual(self.get(path, page=2, page_size=2, limit=1, offset=0)['items'], second['items'])
                self.assertEqual(self.get(path, page_size=2)['items'], first['items'])
                self.assertEqual(self.get(path, limit=2, offset=1)['items'], all_rows['items'][1:3])
                if path == 'commissions':
                    self.assertEqual(first['summary'], last['summary'])
                    self.assertEqual(float(first['summary']['total_earned']), 5)

    def test_invalid_parameters_fail_on_every_record_endpoint(self):
        for path in self.paths:
            for params in ({'page':0}, {'page':-1}, {'page':'abc'}, {'page':100000001},
                           {'page_size':0}, {'page_size':101}, {'page_size':'abc'}):
                with self.subTest(path=path,params=params):
                    response=self.client.get('/api/app/v1/'+path,params=params,headers=self.headers)
                    self.assertEqual(response.status_code,422,response.text)

    def test_filter_counts_and_empty_page_metadata(self):
        first=self.get('subsidies',status=1,page=1,page_size=1)
        self.assertEqual((first['total'],first['total_pages'],first['has_more']),(2,2,True))
        second=self.get('subsidies',status=1,page=2,page_size=1)
        self.assertNotEqual(first['items'][0]['id'],second['items'][0]['id'])
        self.assertFalse(second['has_more'])
        for path in ('ads/history','subsidies','subsidy-campaigns'):
            empty=self.get(path,game_id=2,page=1,page_size=2)
            self.assertEqual((empty['items'],empty['total'],empty['total_pages'],empty['has_more']),([],0,0,False))
