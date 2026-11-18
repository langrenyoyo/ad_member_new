import json
from unittest.mock import patch
from sqlalchemy import select, func
from test_secondary_ads import SecondaryAdTests
from app import main_from_txt as m


class PreloadTests(SecondaryAdTests):
    def test_preload_dedup_quote_and_no_reward_or_impression(self):
        self.configure()
        body={**self.body(), 'event':'preload','status':'loaded','duration_ms':500,
              'e_c_cny':'cipher','s_id':'key'}
        proof={'prices':[{'currency':'CNY','ecpm':'120'}]}
        with patch('app.taku_ecpm.verify_ecpm',return_value=proof):
            response=self.client.post('/api/app/v1/ads/preload-events',json=body,headers=self.auth)
        self.assertEqual(response.status_code,202,response.text)
        self.assertTrue(response.json()['data']['recorded'])
        self.assertFalse(self.client.post('/api/app/v1/ads/preload-events',json=body,headers=self.auth).json()['data']['recorded'])
        headers=self.admin_headers()
        result=self.client.get('/api/v1/games/1/ad-preloads',headers=headers).json()
        self.assertEqual(result['total'],1)
        self.assertEqual(result['items'][0]['ecpm_cny'],'120')
        with self.factory() as s:
            s.add(m.AppAdEvent(event_id='preload:another-game',ad_session_id='preload_10_other',member_id=1,
                event_type='ad_preload',result_json='{}'))
            s.commit()
        self.assertEqual(self.client.get('/api/v1/games/1/ad-preloads',headers=headers).json()['total'],1)
        with self.factory() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AdRecord)),0)
            self.assertEqual(s.scalar(select(func.count()).select_from(m.AppAdSession)),0)
            self.assertEqual(s.get(m.Member,1).coin,0)
        self.assertEqual(self.client.post('/api/app/v1/ads/preload-events',json={**body,'ad_unit_id':'wrong'},headers=self.auth).status_code,422)
        self.assertEqual(self.client.get('/api/v1/games/1/ad-preloads',headers=self.auth).status_code,401)
