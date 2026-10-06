"""Device risk browser check with isolated database; no cloud calls."""
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
        from app import device_risk as r
        os.environ.update(ALIBABA_CLOUD_ACCESS_KEY_ID='ui-test', ALIBABA_CLOUD_ACCESS_KEY_SECRET='ui-test')
        with m.SessionLocal() as s:
            admin=m.AdminUser(username='risk-ui',role='risk',status=1,password_hash='unused',password_salt='unused')
            s.add_all([admin,m.Agent(id=1,name='UI Agent'),m.Game(id=1,agent_id=1,name='Risk UI Game')])
            s.add(r.RiskDevice(id=1,game_id=1,device_key='a'*64))
            s.commit()
            token=m.create_access_token(admin)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        program = "from app import main_from_txt as m; import uvicorn; uvicorn.run(m.app,host='127.0.0.1',port="+str(port)+",lifespan='off')"
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
                page.goto(origin+'/#risk-devices')
                page.locator('[data-picker] input').fill('1')
                page.locator('[data-picker] button').click()
                page.locator('form[data-rule]').wait_for()
                page.locator('[data-rule] [name=enabled]').check()
                page.locator('[data-rule] [name=limit_enabled]').check()
                page.locator('[data-rule] [name=daily_limit]').fill('3')
                page.locator('[data-rule] button').click()
                page.wait_for_function("document.querySelector('[data-message]').textContent.includes('已保存')")
                page.locator('[data-device] [name=mode]').select_option('restrict')
                page.locator('[data-device] [name=reason]').fill('UI verification')
                page.locator('[data-device] button').click()
                page.wait_for_function("document.querySelector('[data-message]').textContent.includes('审计')")
                page.reload()
                page.locator('[data-picker] input').fill('1')
                page.locator('[data-picker] button').click()
                page.locator('form[data-rule]').wait_for()
                assert page.locator('[data-rule] [name=enabled]').is_checked()
                assert page.locator('[data-rule] [name=daily_limit]').input_value()=='3'
                page.locator('[data-device]').wait_for()
                assert page.locator('[data-device] [name=mode]').input_value()=='restrict'
                assert not errors, errors
                browser.close()
            with m.SessionLocal() as s:
                assert s.get(r.DeviceRule,1).daily_limit==3
                assert s.get(r.RiskDevice,1).override=='restrict'
            print('Device risk settings/override/persistence browser check passed.')
        finally:
            process.terminate(); process.wait(timeout=15); m.engine.dispose()


if __name__ == '__main__': main()
