import json
from io import BytesIO
from unittest.mock import patch
from app.wechat_profile import display_name, fetch_profile


def test_nickname_symbols_and_profile_identity():
    assert display_name(' 张三😀\u200b\x00 ') == '张三???'
    assert display_name('Alice_张三-1') == 'Alice_张三-1'
    data={'openid':'own','nickname':'昵称😀','headimgurl':'https://example.com/avatar'}
    with patch('app.wechat_profile.urlopen',return_value=BytesIO(json.dumps(data).encode())):
        assert fetch_profile({'openid':'own','access_token':'token'})['nickname']=='昵称?'
    with patch('app.wechat_profile.urlopen',return_value=BytesIO(json.dumps(data).encode())):
        assert fetch_profile({'openid':'other','access_token':'token'})=={}
    with patch('app.wechat_profile.urlopen',side_effect=OSError):
        assert fetch_profile({'openid':'own','access_token':'token'})=={}
