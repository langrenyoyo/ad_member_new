import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.request_audit import AppRequestAudit


class RequestAuditTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(AppRequestAudit)

        @app.post('/api/app/v1/echo')
        async def echo(request: Request):
            return await request.json()

        @app.post('/api/app/v1/validate')
        async def validate(payload: dict):
            return payload

        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_preserves_body_and_redacts_nested_secrets(self):
        import json
        body = {'game_id': 238, 'device_id': 'phone-test', 'password': 'private-value',
                'nested': [{'aliyun_device_token': 'secret-value', 'event_id': 'event-1'}]}
        with patch('app.request_audit.logger.info') as log:
            response = self.client.post('/api/app/v1/echo', json=body)
        self.assertEqual(response.json(), body)
        record = json.loads(log.call_args.args[0])
        self.assertEqual(record['audit_id'], response.headers['x-app-audit-id'])
        self.assertEqual(record['status'], 200)
        self.assertEqual(record['body']['nested'][0]['event_id'], 'event-1')
        self.assertNotIn('private-value', log.call_args.args[0])
        self.assertNotIn('secret-value', log.call_args.args[0])

    def test_oversize_does_not_change_application_input(self):
        with patch('app.request_audit.logger.info') as log:
            response = self.client.post('/api/app/v1/echo', json={'text': 'a' * 40000})
        self.assertEqual(len(response.json()['text']), 40000)
        self.assertIn('oversize_omitted', log.call_args.args[0])
        self.assertLess(len(log.call_args.args[0]), 1000)

    def test_invalid_json_does_not_expose_partial_secret(self):
        with patch('app.request_audit.logger.info') as log:
            response = self.client.post('/api/app/v1/validate', content='{"password":"hidden',
                                        headers={'content-type': 'application/json'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('invalid_json_omitted', log.call_args.args[0])
        self.assertNotIn('hidden', log.call_args.args[0])

    def test_logger_failure_does_not_break_response(self):
        with patch('app.request_audit.logger.info', side_effect=OSError('disk')):
            response = self.client.post('/api/app/v1/echo', json={'ok': True})
        self.assertEqual(response.status_code, 200)
