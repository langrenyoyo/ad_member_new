"""Fetch an authorized WeChat profile without trusting client-supplied names."""
import json
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def display_name(value):
    value = unicodedata.normalize('NFC', str(value or ''))
    return ''.join(c if unicodedata.category(c)[0] in 'LNMP' or c == ' ' else '?'
                   for c in value).strip()[:128]


def fetch_profile(token_result):
    if not token_result.get('access_token') or not token_result.get('openid'):
        return {}
    query = urlencode({'access_token': token_result['access_token'], 'openid': token_result['openid'], 'lang':'zh_CN'})
    try:
        with urlopen(Request('https://api.weixin.qq.com/sns/userinfo?'+query), timeout=8) as response:
            data = json.loads(response.read(65536).decode('utf-8'))
        if not isinstance(data, dict) or data.get('errcode') or data.get('openid') != token_result['openid']:
            return {}
        return {'nickname': display_name(data.get('nickname')), 'avatar_url':str(data.get('headimgurl') or '')[:2048]}
    except (OSError, ValueError, TypeError):
        return {}  # profile unavailability must not discard successful login
