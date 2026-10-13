"""Production can serve non-payment features without enabling payouts."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProductionStartupTests(unittest.TestCase):
    def test_unconfigured_payment_does_not_block_production_import(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(APP_ENV='production', JWT_SECRET='test-production-secret-' * 3,
                       ADMIN_PASSWORD='Production-Test-123!', PAYMENT_PROVIDER='',
                       DATABASE_URL='sqlite:///' + Path(directory, 'test.db').as_posix())
            result = subprocess.run(
                [sys.executable, '-c',
                 'from app import main_from_txt as m; '
                 'assert m.APP_ENV == "production"; '
                 'assert not m.configured_provider().available'],
                cwd=Path(__file__).resolve().parents[1], env=env,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            env['JWT_SECRET'] = 'development-only-change-this-secret'
            rejected = subprocess.run(
                [sys.executable, '-c', 'from app import main_from_txt'],
                cwd=Path(__file__).resolve().parents[1], env=env,
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
