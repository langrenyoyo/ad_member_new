"""ZTHY template SMS transport. Credentials never leave the backend."""
import hashlib
import json
import os
import time
from urllib.request import Request, urlopen

from fastapi import HTTPException


def send_sms(phone: str, code: str) -> None:
    username, password, signature, template = [os.getenv(key, '').strip() for key in (
        'SMS_ZTHY_USERNAME', 'SMS_ZTHY_PASSWORD', 'SMS_ZTHY_SIGNATURE', 'SMS_ZTHY_TEMPLATE_ID')]
    variable = os.getenv('SMS_ZTHY_CODE_VARIABLE', 'code').strip()
    if not all((username, password, signature, template, variable)):
        raise HTTPException(503, '短信服务尚未配置')
    try:
        template_id = int(template)
        variables = json.loads(os.getenv('SMS_ZTHY_TEMPLATE_PARAMS', '').strip() or '{}')
        if template_id <= 0 or not isinstance(variables, dict):
            raise ValueError('Invalid template configuration')
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in variables.items()):
            raise ValueError('Template parameters must be strings')
    except (ValueError, TypeError):
        raise HTTPException(503, '短信服务配置有误') from None
    variables[variable] = code
    timestamp = int(time.time())
    first = hashlib.md5(password.encode('utf-8')).hexdigest()
    signed = hashlib.md5((first + str(timestamp)).encode('utf-8')).hexdigest()
    payload = {'username': username, 'password': signed, 'tKey': timestamp,
               'signature': signature, 'tpId': template_id,
               'records': [{'mobile': phone, 'tpContent': variables}]}
    request = Request('https://api.mix2.zthysms.com/v2/sendSmsTp',
                      data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                      headers={'Content-Type': 'application/json; charset=UTF-8'}, method='POST')
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read(65536))
    except (OSError, ValueError):
        raise HTTPException(503, '短信服务暂不可用') from None
    # A batch may return 200 while rejecting the only recipient.
    if (not isinstance(result, dict) or type(result.get('code')) is not int
            or result['code'] != 200 or not result.get('msgId') or result.get('invalidList')):
        raise HTTPException(503, '短信发送失败，请稍后重试')
