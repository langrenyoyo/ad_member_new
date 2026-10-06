"""RSA2 public-key mode for Alipay unified transfer and signed order query."""
import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


@dataclass(frozen=True)
class PaymentResult:
    state: str = 'processing'
    message: str = ''
    order_id: str = ''
    provider: str = 'alipay'

    @property
    def confirmed(self):
        return self.state == 'succeeded'


class PaymentProvider:
    name = 'unconfigured'
    available = False
    configuration_error = '支付宝尚未配置'

    def transfer(self, withdrawal_ids):
        return PaymentResult(provider=self.name)


def canonical(params):
    return '&'.join(f'{key}={params[key]}' for key in sorted(params) if params[key] not in (None, ''))


class AlipayProvider(PaymentProvider):
    name = 'alipay'
    available = True

    def __init__(self):
        self.app_id = os.environ['ALIPAY_APP_ID'].strip()
        self.environment = os.getenv('ALIPAY_ENV', 'sandbox')
        if self.environment not in ('sandbox', 'production'): raise ValueError('ALIPAY_ENV')
        if os.getenv('APP_ENV') == 'production' and self.environment != 'production': raise ValueError('production environment required')
        self.gateway = ('https://openapi.alipay.com/gateway.do' if self.environment == 'production'
                        else 'https://openapi-sandbox.dl.alipaydev.com/gateway.do')
        self.private_key = serialization.load_pem_private_key(Path(os.environ['ALIPAY_PRIVATE_KEY_PATH']).read_bytes(), password=None)
        self.public_key = serialization.load_pem_public_key(Path(os.environ['ALIPAY_PUBLIC_KEY_PATH']).read_bytes())
        if not isinstance(self.private_key, rsa.RSAPrivateKey) or not isinstance(self.public_key, rsa.RSAPublicKey):
            raise ValueError('RSA keys required')
        if self.private_key.key_size < 2048 or self.public_key.key_size < 2048: raise ValueError('RSA2 requires 2048 bits')
        self.timeout = min(30, max(1, float(os.getenv('ALIPAY_TIMEOUT', '10'))))
        self.scope = self.environment + ':' + self.app_id
        self.notify_url = os.getenv('ALIPAY_NOTIFY_URL', '').strip()
        if self.notify_url and not self.notify_url.startswith('https://'): raise ValueError('HTTPS callback required')
        self.configuration_error = ''

    def call(self, method, biz):
        params = {'app_id': self.app_id, 'method': method, 'format': 'JSON', 'charset': 'utf-8',
            'sign_type': 'RSA2', 'timestamp': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0', 'biz_content': json.dumps(biz, ensure_ascii=False, separators=(',', ':'))}
        if method == 'alipay.fund.trans.uni.transfer' and getattr(self, 'notify_url', ''):
            params['notify_url'] = self.notify_url
        params['sign'] = base64.b64encode(self.private_key.sign(canonical(params).encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
        request = Request(self.gateway, data=urlencode(params).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'})
        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024: raise ValueError('response too large')
        raw = raw.decode('utf-8')
        envelope = json.loads(raw)
        # Verify the ORIGINAL JSON slice: reserialization changes whitespace
        # and escaping, which would not match Alipay's signature.
        key = method.replace('.', '_') + '_response'
        match = re.search(r'"' + re.escape(key) + r'"\s*:\s*', raw)
        if match is None or not envelope.get('sign'): raise ValueError('unsigned response')
        value, end = json.JSONDecoder().raw_decode(raw[match.end():])
        self.public_key.verify(base64.b64decode(envelope['sign'], validate=True),
            raw[match.end():match.end()+end].encode(), padding.PKCS1v15(), hashes.SHA256())
        if value != envelope[key]: raise ValueError('ambiguous response')
        return value

    def _result(self, result, order):
        if result.get('code') != '10000':
            # A rejected HTTP/API request is not proof the merchant order was
            # never accepted. Query instead of releasing frozen funds.
            return PaymentResult(message='支付宝返回 ' + str(result.get('sub_code') or result.get('code') or 'UNKNOWN')[:128])
        if result.get('out_biz_no') != order['out_biz_no']:
            return PaymentResult(message='支付宝订单号不匹配，待核对')
        if result.get('status') == 'SUCCESS':
            order_id = str(result.get('order_id') or '')
            if not order_id: return PaymentResult(message='支付宝未返回订单号')
            return PaymentResult('succeeded', order_id=order_id)
        if result.get('status') == 'FAIL':
            return PaymentResult('failed', '支付宝确认转账失败')
        return PaymentResult(message='支付宝处理中')

    def send(self, order):
        try:
            result = self.call('alipay.fund.trans.uni.transfer', {
                'out_biz_no': order['out_biz_no'], 'trans_amount': f"{order['amount_cents']//100}.{order['amount_cents']%100:02d}",
                'product_code': 'TRANS_ACCOUNT_NO_PWD', 'biz_scene': 'DIRECT_TRANSFER', 'order_title': '金币提现',
                'payee_info': {'identity': order['account'], 'identity_type': 'ALIPAY_LOGON_ID', 'name': order['real_name']}})
            return self._result(result, order)
        except Exception:
            # Do not expose account details, private key paths or raw replies.
            return PaymentResult(message='转账结果未确认，请查询支付宝订单')

    def query(self, order):
        try:
            result = self.call('alipay.fund.trans.common.query', {'out_biz_no': order['out_biz_no'],
                'product_code': 'TRANS_ACCOUNT_NO_PWD', 'biz_scene': 'DIRECT_TRANSFER'})
            if result.get('sub_code') in ('ORDER_NOT_EXIST', 'ORDER_NOT_EXISTS'):
                return PaymentResult('not_found', '支付宝暂未找到该订单，可使用原商户订单号重试')
            return self._result(result, order)
        except Exception:
            return PaymentResult(message='查询失败，资金保持冻结，稍后重试')

    def verify_notification(self, params):
        try:
            if params.get('app_id') != self.app_id or params.get('sign_type') != 'RSA2': return False
            signature = base64.b64decode(params['sign'], validate=True)
            values = {k: v for k, v in params.items() if k not in ('sign', 'sign_type')}
            self.public_key.verify(signature, canonical(values).encode(), padding.PKCS1v15(), hashes.SHA256())
            return True
        except Exception:
            return False


def configured_provider():
    if os.getenv('PAYMENT_PROVIDER', '').lower() != 'alipay': return PaymentProvider()
    try:
        return AlipayProvider()
    except Exception:
        result = PaymentProvider()
        result.configuration_error = '支付宝配置缺失或无效，请检查 APP_ID、环境及 RSA2 密钥文件'
        return result
