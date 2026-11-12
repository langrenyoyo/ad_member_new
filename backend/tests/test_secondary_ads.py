"""Real temporary database/API checks for non-rewarding secondary ad telemetry."""
import json
import unittest
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select, func
import test_member_policy as fixtures
from app import main_from_txt as m


class SecondaryAdTests(unittest.TestCase):
    setUp = fixtures.MemberPolicyTests.setUp
    tearDown = fixtures.MemberPolicyTests.tearDown
    admin_headers = fixtures.MemberPolicyTests.admin_headers

    def configure(self):
        with self.factory() as s:
            game = s.get(m.Game, 1)
            game.ad_status = 1
            game.settings_json = json.dumps({'ad_config': {'enabled': True, 'provider': 'taku',
                'placements': {k: {'unit_id': 'unit-'+k} for k in ('rewarded','banner','splash','interstitial','native')}}})
            s.commit()

    def body(self, kind='interstitial', **changes):
        return {'game_id':1,'impression_id':str(uuid4()),'placement':kind,'ad_type':kind,
            'ad_unit_id':'unit-'+kind,'event':'shown','occurred_at':m.now().isoformat(),
            'title':'示例游戏广告','app_name':'示例游戏','app_package':'example.ad.game',
            'creative_id':'creative-123','source_id':'source-456','network':'快手', **changes}

    def post(self, body, headers=None):
        return self.client.post('/api/app/v1/ads/secondary-events',headers=headers or self.auth,json=body)

    def test_all_four_types_record_metadata_without_rewards(self):
        self.configure()
        for kind, fu in [('splash',1),('banner',2),('interstitial',3),('native',4)]:
            response=self.post(self.body(kind))
            self.assertEqual(response.status_code,202,response.text)
        with self.factory() as s:
            rows=s.scalars(select(m.AdRecord).order_by(m.AdRecord.fu_type)).all()
            self.assertEqual([r.fu_type for r in rows],[1,2,3,4])
            self.assertTrue(all(r.is_fu==1 and r.ad_type=='副广' and r.coin==0 for r in rows))
            self.assertEqual(s.get(m.Member,1).coin,0)
            self.assertEqual(s.scalar(select(func.count()).select_from(m.CoinLog)),0)
            self.assertEqual(s.scalar(select(func.count()).select_from(m.member_policy.RewardLedger)),0)
        history=self.client.get('/api/app/v1/ads/history',headers=self.auth).json()['data']
        self.assertEqual(history['total'],0)
        self.assertEqual(history['items'],[])
        admin=self.client.get('/api/v1/ads',headers=self.admin_headers(),params={'is_fu':1}).json()
        self.assertEqual(admin['total'],4)
        self.assertTrue(all(r['ad_app_package']=='example.ad.game' and r['ad_content_status']=='reported' for r in admin['items']))

    def test_retry_dedup_and_two_actual_impressions_are_separate(self):
        self.configure();body=self.body()
        first=self.post(body)
        self.assertTrue(first.json()['data']['recorded'])
        self.assertFalse(self.post(body).json()['data']['recorded'])
        self.assertEqual(self.post({**body,'event':'clicked'}).status_code,202)
        self.assertEqual(self.post({**body,'event':'closed'}).status_code,202)
        self.assertEqual(self.post(self.body()).status_code,202)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AdRecord)),2)
        self.assertEqual(self.client.get('/api/app/v1/ads/history',headers=self.auth).json()['data']['total'],0)
        with self.factory() as s:
            closed=s.scalar(select(m.AppAdSession).where(m.AppAdSession.status=='closed'))
            self.assertIsNotNone(closed.impressed_at)
            events=s.scalars(select(m.AppAdEvent).where(m.AppAdEvent.ad_session_id==closed.id,
                m.AppAdEvent.event_type=='client_metadata')).all()
            self.assertEqual({json.loads(event.result_json)['event'] for event in events}, {'shown','clicked','closed'})

    def test_out_of_order_close_then_show_keeps_closed_and_records_display(self):
        self.configure();body=self.body(event='closed')
        self.assertEqual(self.post(body).status_code,202)
        self.assertEqual(self.client.get('/api/app/v1/ads/history',headers=self.auth).json()['data']['total'],0)
        self.assertEqual(self.post({**body,'event':'shown'}).status_code,202)
        self.assertEqual(self.client.get('/api/app/v1/ads/history',headers=self.auth).json()['data']['total'],0)
        with self.factory() as s:
            row=s.scalar(select(m.AppAdSession))
            self.assertEqual(row.status,'closed')
            self.assertIsNotNone(row.impressed_at)
            self.assertIsNone(row.coin_log_id)

    def test_type_unit_and_time_cannot_be_forged_as_reward(self):
        self.configure()
        for changes in [{'ad_type':'rewarded'},{'placement':'banner'}, {'ad_unit_id':'wrong'},
                        {'occurred_at':(m.now()-timedelta(days=2)).isoformat()},
                        {'occurred_at':m.now().replace(tzinfo=None).isoformat()}]:
            self.assertEqual(self.post(self.body(**changes)).status_code,422)
        body=self.body();self.post(body)
        self.assertEqual(self.post({**body,'ad_type':'banner','placement':'banner','ad_unit_id':'unit-banner'}).status_code,409)
        sid=self.post(body).json()['data']['ad_session_id']
        with self.factory() as s:
            # Even if a token leaked from elsewhere, secondary telemetry cannot settle.
            s.get(m.AppAdSession,sid).session_token_hash=m._token_hash('test-secret-value-123456789')
            s.commit()
        response=self.client.post('/api/app/v1/ads/'+sid+'/complete',headers=self.auth,
            json={'event_id':'forged-complete','session_token':'test-secret-value-123456789'})
        self.assertEqual(response.status_code,409,response.text)

    def test_member_scope_and_same_device_event_never_overwrite_other_member(self):
        self.configure();body=self.body()
        self.post(body)
        self.assertEqual(self.client.get('/api/app/v1/ads/history',headers=self.other).json()['data']['total'],0)
        self.assertEqual(self.post(body,self.other).status_code,202)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AdRecord)),2)
            self.assertEqual(s.scalar(select(func.count(func.distinct(m.AppAdSession.request_id)))),2)

    def test_unknown_content_is_explicit_and_does_not_invent_name(self):
        self.configure();self.post(self.body(title='',app_name='',app_package='',creative_id=''))
        row=self.client.get('/api/v1/ads',headers=self.admin_headers()).json()['items'][0]
        self.assertEqual(row['ad_title'],'')
        self.assertEqual(row['ad_content_status'],'sdk_not_provided')
        self.assertEqual(row['ad_network'],'快手')

    def test_secondary_impressions_do_not_change_reward_label_denominator(self):
        self.configure();self.post(self.body())
        with self.factory() as s:
            summary=m.member_insights.label_summary(s,1,m.member_policy.policy(s,1))
            self.assertEqual(summary['total'],0)

    def test_rewarded_content_can_retry_after_session_expiry_without_changing_reward_state(self):
        with self.factory() as s:
            s.add(m.AppAdSession(id='reward-content',member_id=1,game_id=1,agent_id=1,
                request_id='req-reward-content',ad_type='rewarded',provider='taku',status='impressed',
                session_token_hash=m._token_hash('secret'),impressed_at=m.now()-timedelta(minutes=15),expires_at=m.now()-timedelta(minutes=10)))
            s.add(m.AdRecord(user_id=1,game_id=1,agent_id=1,request_id='req-reward-content'))
            s.commit()
        body={'session_token':'secret','event':'shown','title':'真实素材示例',
              'app_name':'应用示例','creative_id':'material-456','network':'快手'}
        response=self.client.post('/api/app/v1/ads/reward-content/metadata',headers=self.auth,json=body)
        self.assertEqual(response.status_code,200,response.text)
        with self.factory() as s:
            self.assertEqual(s.get(m.AppAdSession,'reward-content').status,'impressed')
            self.assertEqual(s.get(m.Member,1).coin,0)
        row=self.client.get('/api/app/v1/ads/history',headers=self.auth).json()['data']['items'][0]
        self.assertEqual(row['is_fu'],0)
        self.assertIsNone(row['fu_type'])
        self.assertEqual(row['ad_title'],'真实素材示例')
        admin=self.client.get('/api/v1/ads',headers=self.admin_headers()).json()['items'][0]
        self.assertEqual(admin['ad_creative_id'],'material-456')
        self.assertEqual(admin['ad_network'],'快手')

if __name__=='__main__':unittest.main()
