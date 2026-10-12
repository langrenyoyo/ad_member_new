"""Run the real API against a disposable database for adb reverse device tests.

Set DEVICE_TEST_PASSWORD, then run this script. No production credentials,
advertising placements or payment providers are loaded.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18080)
    parser.add_argument('--simulated-payments', action='store_true',
                        help='Disposable local payment simulation only, never Alipay')
    args = parser.parse_args()
    password = os.environ.get('DEVICE_TEST_PASSWORD')
    if not password or len(password) < 8:
        raise SystemExit('Set DEVICE_TEST_PASSWORD (at least 8 characters)')
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', args.port))
        except OSError:
            raise SystemExit(f'Port {args.port} is occupied; inspect the existing server before restarting.')
    with tempfile.TemporaryDirectory(prefix='ad-member-device-') as directory:
        os.environ.update(
            DATABASE_URL='sqlite:///' + (Path(directory) / 'device.db').as_posix(),
            APP_ENV='development', JWT_SECRET=secrets.token_urlsafe(48),
            ADMIN_PASSWORD=secrets.token_urlsafe(24), PAYMENT_PROVIDER='',
            TAKU_SEC_KEY='',
        )
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
        from app import main_from_txt as m
        import uvicorn
        if args.simulated_payments:
            from app.payment import PaymentResult
            class Simulator:
                available = True
                name = 'local-device-simulator'
                scope = 'local-device-simulator'
                environment = 'simulation'
                configuration_error = ''
                def send(self, order):
                    return PaymentResult(message='Local simulation: awaiting confirmation')
                def query(self, order):
                    return PaymentResult('succeeded', order_id='SIM-' + order['out_biz_no'])
                def verify_notification(self, params):
                    return False
            simulator = Simulator()
            m.configured_provider = lambda: simulator
        m.Base.metadata.create_all(m.engine)
        with m.SessionLocal() as session:
            session.add(m.Agent(id=1, name='Device test'))
            session.add(m.Game(id=1, name='Device test', agent_id=1, status=1,
                tixian_price='1' if args.simulated_payments else '',
                tixian_coin='1' if args.simulated_payments else '', exchange_num=10,
                settings_json=json.dumps({'member_policy': {'announcement': 'Isolated device test'}})))
            hashed, salt = m.hash_password(password)
            session.add(m.Member(id=1, username='13800000000', name='Device test',
                game_id=1, agent_id=1, status=1, password_hash=hashed, password_salt=salt))
            if args.simulated_payments:
                session.flush()
                session.get(m.Member,1).coin = 5
                session.add(m.CoinLog(user_id=1,game_id=1,agent_id=1,coin_before=0,
                    coin=5,coin_after=5,type=1,remark='Local device simulation opening credit'))
                session.add(m.payouts.AlipayAccount(member_id=1,
                    account='device-simulation@example.invalid',real_name='DeviceSimulator'))
            session.commit()
        print(f'Disposable API: http://127.0.0.1:{args.port} (no live payments or ads)', flush=True)
        print(f'Disposable database: {directory}', flush=True)
        try:
            uvicorn.run(m.app, host='127.0.0.1', port=args.port, access_log=False)
        finally:
            m.engine.dispose()


if __name__ == '__main__':
    main()
