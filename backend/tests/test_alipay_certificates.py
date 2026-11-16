import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from app.payment import AlipayProvider, certificate_sn, root_certificate_sn


class CertificateTests(unittest.TestCase):
    def test_certificate_mode_and_key_mismatch(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, 'Test')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(12345)
                .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
                .sign(key, hashes.SHA256()))
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            (p/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            env = {'ALIPAY_APP_ID':'test', 'ALIPAY_ENV':'production',
                'ALIPAY_PRIVATE_KEY_PATH':str(p/'key.pem'), 'ALIPAY_APP_CERT_PATH':str(p/'cert.pem'),
                'ALIPAY_CERT_PATH':str(p/'cert.pem'), 'ALIPAY_ROOT_CERT_PATH':str(p/'cert.pem')}
            with patch.dict(os.environ, env, clear=True):
                provider = AlipayProvider()
                self.assertEqual(provider.certificate_params, {'app_cert_sn':certificate_sn(cert),
                    'alipay_root_cert_sn':root_certificate_sn(p/'cert.pem')})
                self.assertEqual(provider.public_key.public_numbers(), key.public_key().public_numbers())
                other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                (p/'key.pem').write_bytes(other.private_bytes(serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                with self.assertRaisesRegex(ValueError, 'mismatch'):
                    AlipayProvider()
