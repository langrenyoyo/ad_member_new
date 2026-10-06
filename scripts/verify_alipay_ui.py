"""Browser check with an isolated DB and a fake provider; never calls Alipay."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ.update(DATABASE_URL='sqlite:///' + str(Path(directory) / 'ui.db'),
                          JWT_SECRET='isolated-alipay-ui-secret-at-least-32-chars', APP_ENV='development')
        from app import main_from_txt as m
        from playwright.sync_api import sync_playwright
        m.Base.metadata.create_all(m.engine)
        with m.SessionLocal() as s:
            admin = m.AdminUser(username='ui-admin', role='superadmin', password_hash='unused', password_salt='unused')
            s.add_all([admin, m.Agent(id=1, name='UI Agent'), m.Game(id=1, agent_id=1, name='UI Game'),
                m.Member(id=1, username='UI user', agent_id=1, game_id=1, coin=80, freeze_coin=20)])
            item = m.Withdrawal(user_id=1, game_id=1, agent_id=1, status=0, plan_status=0,
                exchange_value=5, exchange_type=1, receive_tel='13000000000', receive_name='UI User')
            s.add(item); s.flush()
            s.add(m.payouts.Payout(withdrawal_id=item.id, member_id=1, game_id=1, request_key='browser-test',
                amount_cents=500, coin_cost=20, account='13000000000', real_name='UI User', out_biz_no='UI_ORDER', provider_scope=''))
            s.commit()
            token = m.create_access_token(admin)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        program = '''
from app import main_from_txt as m
from app.payment import PaymentResult
import uvicorn
class Fake:
    available=True
    name='alipay'
    environment='isolated-test'
    def send(self,order): return PaymentResult('succeeded',order_id='UI_ALIPAY_ORDER')
    def query(self,order): return self.send(order)
m.configured_provider=lambda:Fake()
uvicorn.run(m.app,host='127.0.0.1',port=PORT,lifespan='off')
'''.replace('PORT', str(port))
        process = subprocess.Popen([sys.executable, '-c', program], cwd=ROOT,
            env={**os.environ, 'PYTHONPATH': str(ROOT / 'backend')}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(origin + '/api/health', timeout=1).close(); break
                except OSError: time.sleep(.2)
            else: raise RuntimeError('Isolated server failed to start')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1500, 'height': 1000})
                errors=[]
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script('localStorage.setItem("admin_access_token", '+json.dumps(token)+')')
                page.goto(origin+'/#withdrawals')
                page.get_by_role('cell', name='5.00元', exact=True).wait_for()
                page.locator('[data-review-action=approve]').click()
                page.locator('.withdrawal-confirm-ok').click()
                page.locator('[data-payout-action=transfer]').wait_for()
                page.locator('[data-payout-action=transfer]').click()
                page.locator('.withdrawal-confirm-ok').click()
                page.get_by_role('cell', name='支付宝已确认到账', exact=True).wait_for()
                page.reload()
                page.get_by_role('cell', name='支付宝已确认到账', exact=True).wait_for()
                assert not errors, errors
                browser.close()
            with m.SessionLocal() as s:
                member=s.get(m.Member,1)
                assert (member.coin,member.freeze_coin)==(80,0)
            print('Alipay review/transfer/status/amount browser check passed (fake provider).')
        finally:
            process.terminate(); process.wait(timeout=15); m.engine.dispose()


if __name__ == '__main__': main()
