"""Bounded, redacted APP JSON request audit to the service log."""
import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone

logger = logging.getLogger('app.request_audit')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.propagate = False


def redact(value, depth=0):
    if depth > 30:
        return '[DEPTH_LIMIT]'
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = ''.join(c for c in key.lower() if c.isalnum())
            private = (any(x in normalized for x in ('password', 'passwd', 'secret', 'token', 'authorization', 'privatekey'))
                       or normalized in {'code', 'account', 'alipayaccount', 'realname', 'receivename',
                                         'receivetel', 'phone', 'mobile', 'email', 'idcard', 'sign', 'signature',
                                         'extradata', 'takuextradata'})
            result[key] = '[REDACTED]' if private else redact(item, depth + 1)
        return result
    if isinstance(value, list):
        return [redact(item, depth + 1) for item in value]
    return value


class AppRequestAudit:
    def __init__(self, app):
        self.app = app
        self.enabled = os.getenv('APP_JSON_AUDIT_ENABLED', '1').lower() not in ('0', 'false', 'off')
        self.limit = 32768

    async def __call__(self, scope, receive, send):
        if (not self.enabled or scope['type'] != 'http'
                or not scope.get('path', '').startswith('/api/app/v1/')):
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        content_type = headers.get(b'content-type', b'').decode('latin1').split(';')[0].strip().lower()
        is_json = content_type == 'application/json' or content_type.endswith('+json')
        audit_id = secrets.token_urlsafe(18)
        scope.setdefault('state', {})['audit_id'] = audit_id
        body = bytearray()
        size = 0
        complete = False
        digest = hashlib.sha256()
        status = 500
        error = None
        start = time.monotonic()

        async def audited_receive():
            nonlocal size, complete
            message = await receive()
            if message['type'] == 'http.request':
                data = message.get('body', b'')
                size += len(data)
                if is_json:
                    digest.update(data)
                    if size <= self.limit:
                        body.extend(data)
                    else:
                        body.clear()
                complete = not message.get('more_body', False)
            return message

        async def audited_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []),
                           (b'x-app-audit-id', audit_id.encode())]}
            await send(message)

        try:
            await self.app(scope, audited_receive, audited_send)
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            try:
                record = {'event': 'app_json_request', 'audit_id': audit_id,
                          'time': datetime.now(timezone.utc).isoformat(), 'method': scope['method'],
                          'path': scope['path'], 'status': status,
                          'duration_ms': round((time.monotonic() - start) * 1000, 2),
                          'received_bytes': size, 'body_complete': complete}
                if error:
                    record['error_type'] = error
                if not is_json:
                    record['body_state'] = 'non_json_omitted'
                elif not complete:
                    record['body_state'] = 'not_fully_consumed'
                elif size > self.limit:
                    record['body_state'] = 'oversize_omitted'
                else:
                    try:
                        record['body'] = redact(json.loads(body))
                        record['body_state'] = 'json_redacted'
                    except (ValueError, UnicodeError, RecursionError):
                        record['body_state'] = 'invalid_json_omitted'
                if is_json and complete:
                    record['body_sha256'] = digest.hexdigest()
                logger.info(json.dumps(record, ensure_ascii=False, separators=(',', ':')))
            except Exception:
                # Logging failure must never change the business response.
                pass
