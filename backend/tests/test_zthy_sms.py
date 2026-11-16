import hashlib
import json
import unittest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from app import zthy_sms as sms


class ZthySmsTests(unittest.TestCase):
    def setUp(self):
        env = {'SMS_ZTHY_USERNAME': 'test-account', 'SMS_ZTHY_PASSWORD': 'test-password',
               'SMS_ZTHY_SIGNATURE': '【禾合】', 'SMS_ZTHY_TEMPLATE_ID': '183',
               'SMS_ZTHY_CODE_VARIABLE': 'var1', 'SMS_ZTHY_TEMPLATE_PARAMS': '{"var2":"5"}'}
        self.env = patch.dict(sms.os.environ, env, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def response(self, data):
        mock = MagicMock()
        mock.__enter__.return_value.read.return_value = json.dumps(data).encode()
        return mock

    @patch.object(sms.time, 'time', return_value=1700000000)
    @patch.object(sms, 'urlopen')
    def test_signed_template_payload_and_success(self, transport, clock):
        transport.return_value = self.response({'code': 200, 'msgId': 'accepted', 'invalidList': []})
        sms.send_sms('13800000000', '012345')
        request = transport.call_args.args[0]
        body = json.loads(request.data)
        expected = hashlib.md5((hashlib.md5(b'test-password').hexdigest()+'1700000000').encode()).hexdigest()
        self.assertEqual(body, {'username': 'test-account', 'password': expected, 'tKey': 1700000000,
            'signature': '【禾合】', 'tpId': 183,
            'records': [{'mobile': '13800000000', 'tpContent': {'var1': '012345', 'var2': '5'}}]})
        self.assertEqual(request.full_url, 'https://api.mix2.zthysms.com/v2/sendSmsTp')
        self.assertEqual(transport.call_args.kwargs['timeout'], 10)
        self.assertNotIn(b'test-password', request.data)

    @patch.object(sms, 'urlopen')
    def test_failed_or_partial_acceptance_not_reported_as_success(self, transport):
        for data in ({'code': 4009, 'msg': 'sensitive provider detail'},
                     {'code': 200, 'msgId': 'x', 'invalidList': [{'mobile': '13800000000'}]},
                     {'code': 200}, [], None):
            with self.subTest(data=data):
                transport.return_value = self.response(data)
                with self.assertRaises(HTTPException) as raised:
                    sms.send_sms('13800000000', '123456')
                self.assertEqual(raised.exception.status_code, 503)
                self.assertNotIn('sensitive', raised.exception.detail)

    @patch.object(sms, 'urlopen')
    def test_timeout_and_invalid_json_are_safe(self, transport):
        for failure in (TimeoutError('sensitive'), ValueError('sensitive')):
            transport.side_effect = failure
            with self.assertRaises(HTTPException) as raised:
                sms.send_sms('13800000000', '123456')
            self.assertNotIn('sensitive', raised.exception.detail)

    @patch.object(sms, 'urlopen')
    def test_invalid_configuration_never_sends(self, transport):
        for changes in ({'SMS_ZTHY_PASSWORD': ''}, {'SMS_ZTHY_TEMPLATE_ID': 'bad'},
                        {'SMS_ZTHY_TEMPLATE_PARAMS': '[]'}, {'SMS_ZTHY_TEMPLATE_PARAMS': '{"x":3}'}):
            with patch.dict(sms.os.environ, changes), self.assertRaises(HTTPException):
                sms.send_sms('13800000000', '123456')
        transport.assert_not_called()
