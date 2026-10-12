"""Real isolated API freeze/reject transitions, with device wallet assertions.

The application is created with TestClient, not by a phone tap. Payment is
replaced in this process only; no provider network call is possible.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from unittest.mock import patch


def main():
    path = Path(sys.argv[1]).resolve(strict=True)
    assert path.parent.name.startswith('ad-member-device-') and path.name == 'device.db'
    os.environ.update(DATABASE_URL='sqlite:///' + path.as_posix(), APP_ENV='development',
                      JWT_SECRET=secrets.token_urlsafe(48), PAYMENT_PROVIDER='', TAKU_SEC_KEY='')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app import main_from_txt as m
    from fastapi.testclient import TestClient
    from app.wallet_audit import reconcile
    from app.payment import PaymentResult
    failure_mode = '--failure' in sys.argv[2:]

    class ReviewOnlyProvider:
        available = True
        name = 'device-review-only'
        scope = 'device-review-only'
        sends = 0
        queries = 0
        confirmed_failure = False
        def send(self, order):
            if failure_mode:
                self.sends += 1
                return PaymentResult(message='Simulated timeout; not a payment response')
            raise AssertionError('No transfer allowed')
        def query(self, order):
            if failure_mode:
                self.queries += 1
                return PaymentResult('failed', 'Simulated confirmed failure') if self.confirmed_failure else PaymentResult(message='Simulated pending')
            raise AssertionError('No payment query allowed')

    def adb(*args):
        return subprocess.check_output(['adb', '-s', '47D0220908002529', *args])

    def refresh_wallet():
        adb('shell', 'input', 'tap', '170', '425')
        time.sleep(1)
        adb('shell', 'uiautomator', 'dump', '/sdcard/withdrawal-test.xml')
        root = ET.fromstring(adb('shell', 'cat', '/sdcard/withdrawal-test.xml'))
        return [n.get('text', '') for n in root.iter('node')
                if n.get('package') == 'com.heshangzhilian.yazhiyiji.devtest']

    with m.SessionLocal() as s:
        game = s.get(m.Game, 1)
        assert game.name == 'Device test'
        original = (game.tixian_price, game.tixian_coin, game.exchange_num)
        member = s.get(m.Member, 2)
        before = (member.coin, member.freeze_coin)
        assert before == (2, 0)
        assert s.get(m.payouts.AlipayAccount, 2) is None
        auth = {'Authorization': 'Bearer ' + m._create_app_access_token(member)}
        admin = {'Authorization': 'Bearer ' + m.create_access_token(s.get(m.AdminUser, 1))}
        game.tixian_price, game.tixian_coin, game.exchange_num = '1', '1', 100
        s.add(m.payouts.AlipayAccount(member_id=2, account='device-withdrawal@example.invalid', real_name='DeviceOnly'))
        s.commit()
    client = TestClient(m.app)
    wid = None
    provider = ReviewOnlyProvider()
    try:
        with patch.object(m, 'configured_provider', return_value=provider):
            body = {'game_id':1,'amount_cents':100,'request_key':'device-review-'+secrets.token_hex(8)}
            response = client.post('/api/app/v1/withdrawals', json=body, headers=auth)
            assert response.status_code == 201, response.text
            wid = response.json()['data']['id']
            replay = client.post('/api/app/v1/withdrawals', json=body, headers=auth)
            assert replay.json()['data']['id'] == wid
        current = refresh_wallet()
        assert '1.0' in current and '冻结金币：1.0' in current, current
        assert '待审核' in current, current
        print('Phone displays 1 available, 1 frozen and pending review; replay uses same order', flush=True)
        if failure_mode:
            with patch.object(m, 'configured_provider', return_value=provider):
                base = f'/api/v1/withdrawals/{wid}'
                response = client.post(base+'/approve', headers=admin)
                assert response.status_code == 200, response.text
                for _ in range(2):
                    response = client.post(base+'/transfer', headers=admin)
                    assert response.status_code == 200, response.text
                    assert response.json()['payout']['state'] == 'processing'
                assert (provider.sends, provider.queries) == (1, 1)
                current = refresh_wallet()
                assert '1.0' in current and '冻结金币：1.0' in current, current
                assert any('确认' in t or '处理中' in t for t in current), current
                print('Unknown payment retains freeze; retry queries without second send', flush=True)
                provider.confirmed_failure = True
                for _ in range(2):
                    response = client.post(base+'/query-transfer', headers=admin)
                    assert response.status_code == 200, response.text
                    assert response.json()['payout']['state'] == 'failed'
                assert (provider.sends, provider.queries) == (1, 2)
        else:
            response = client.post(f'/api/v1/withdrawals/{wid}/reject', json={'reason':'Device review test'}, headers=admin)
            assert response.status_code == 200, response.text
            assert client.post(f'/api/v1/withdrawals/{wid}/reject', json={'reason':'Replay'}, headers=admin).status_code == 409
        current = refresh_wallet()
        assert '2.0' in current and '冻结金币：0.0' in current, current
        assert any('失败' in t for t in current) if failure_mode else '已拒绝' in current, current
        with m.SessionLocal() as s:
            member = s.get(m.Member,2)
            assert (member.coin,member.freeze_coin) == before
            assert reconcile(s)['passed']
        print('Phone displays restored balance and final state; internal reconciliation passed', flush=True)
    finally:
        if wid is not None:
            with m.SessionLocal() as s:
                pending = s.get(m.Withdrawal,wid).status == 0
            if pending:
                result = client.post(f'/api/v1/withdrawals/{wid}/reject', json={'reason':'Device test cleanup'}, headers=admin)
                assert result.status_code == 200
            elif failure_mode:
                # Only this in-memory provider can own this disposable order.
                provider.confirmed_failure = True
                with patch.object(m, 'configured_provider', return_value=provider):
                    result = client.post(f'/api/v1/withdrawals/{wid}/transfer', headers=admin)
                    assert result.status_code == 200
                    result = client.post(f'/api/v1/withdrawals/{wid}/query-transfer', headers=admin)
                    assert result.status_code == 200
        with m.SessionLocal() as s:
            game = s.get(m.Game,1)
            game.tixian_price, game.tixian_coin, game.exchange_num = original
            s.delete(s.get(m.payouts.AlipayAccount,2))
            s.commit()
        refresh_wallet()
        client.close()
        m.engine.dispose()
        print('Temporary tier and account restored; test audit trail retained', flush=True)


if __name__ == '__main__':
    main()
