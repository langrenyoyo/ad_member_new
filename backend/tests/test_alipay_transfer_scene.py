import unittest
from unittest.mock import Mock, patch
from app.payment import AlipayProvider


class TransferSceneTests(unittest.TestCase):
    def setUp(self):
        self.provider = AlipayProvider.__new__(AlipayProvider)
        self.provider.call = Mock(return_value={'code':'10000', 'out_biz_no':'immutable-1',
                                                'status':'SUCCESS', 'order_id':'provider-1'})
        self.order = dict(out_biz_no='immutable-1', amount_cents=100,
                          account='test@example.com', real_name='Test')

    def test_missing_scene_does_not_send_or_claim_payment(self):
        with patch.dict('os.environ', {}, clear=True):
            result = self.provider.send(self.order)
        self.assertEqual(result.state, 'processing')
        self.assertIn('ALIPAY_TRANSFER_SCENE_NAME', result.message)
        self.provider.call.assert_not_called()

    def test_scene_and_reports_are_sent_with_original_order_number(self):
        with patch.dict('os.environ', {'ALIPAY_TRANSFER_SCENE_NAME':'approved-test-scene',
             'ALIPAY_TRANSFER_SCENE_REPORT_INFOS':'[{"info_type":"test","info_content":"value"}]',
             'ALIPAY_TRANSFER_SUB_BIZ_SCENE':'REDPACKET'}):
            result = self.provider.send(self.order)
        self.assertEqual(result.state, 'succeeded')
        body = self.provider.call.call_args.args[1]
        self.assertEqual(body['transfer_scene_name'], 'approved-test-scene')
        self.assertEqual(body['transfer_scene_report_infos'], [{'info_type':'test','info_content':'value'}])
        self.assertEqual(body['out_biz_no'], 'immutable-1')
        self.assertEqual(body['business_params'], '{"sub_biz_scene":"REDPACKET"}')
        self.assertEqual(body['payee_info']['identity_type'], 'ALIPAY_LOGON_ID')

    def test_invalid_sub_scene_does_not_send(self):
        with patch.dict('os.environ', {'ALIPAY_TRANSFER_SCENE_NAME':'approved-test-scene',
                                      'ALIPAY_TRANSFER_SUB_BIZ_SCENE':'invalid'}):
            self.assertFalse(self.provider.send(self.order).confirmed)
        self.provider.call.assert_not_called()

    def test_invalid_report_does_not_send(self):
        with patch.dict('os.environ', {'ALIPAY_TRANSFER_SCENE_NAME':'approved-test-scene',
                                      'ALIPAY_TRANSFER_SCENE_REPORT_INFOS':'[{}]'}):
            result = self.provider.send(self.order)
        self.assertFalse(result.confirmed)
        self.provider.call.assert_not_called()
