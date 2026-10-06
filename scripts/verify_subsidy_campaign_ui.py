"""Run the campaign UI against a temporary DB and an isolated HTTP server."""
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
        os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(directory) / 'ui.db')
        os.environ['JWT_SECRET'] = 'isolated-subsidy-ui-secret-at-least-32-chars'
        os.environ['APP_ENV'] = 'development'
        from app import main_from_txt as m
        from playwright.sync_api import sync_playwright
        m.Base.metadata.create_all(m.engine)
        with m.SessionLocal() as session:
            admin = m.AdminUser(username='ui-admin', role='superadmin', password_hash='unused', password_salt='unused')
            session.add_all([admin, m.Agent(id=1, name='UI Agent'), m.Game(id=1, agent_id=1, name='UI Game')])
            session.commit()
            token = m.create_access_token(admin)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'backend')}
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main_from_txt:app',
            '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(origin + '/api/health', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError('Isolated server failed to start')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script('localStorage.setItem("admin_access_token", ' + __import__('json').dumps(token) + ')')
                page.goto(origin + '/#subsidies')
                page.locator('.subsidy-campaigns summary').click()
                page.locator('[data-campaign-new]').click()
                form = page.locator('.campaign-form')
                form.locator('[name=game_id]').fill('1')
                form.locator('[name=title]').fill('UI subsidy campaign')
                form.locator('button[type=submit]').click()
                page.get_by_role('cell', name='UI subsidy campaign', exact=True).wait_for()
                page.locator('[data-campaign-edit]').click()
                page.locator('.campaign-form [name=enabled]').select_option('1')
                page.locator('.campaign-form [name=daily_quota]').fill('60')
                page.locator('.campaign-form button[type=submit]').click()
                page.get_by_role('cell', name='0 / 60', exact=True).wait_for()
                page.reload()
                page.locator('.subsidy-campaigns summary').click()
                page.get_by_role('cell', name='0 / 60', exact=True).wait_for()
                assert page.get_by_role('cell', name='开放', exact=True).count() == 1
                assert not errors, errors
                browser.close()
                print('Campaign UI create/edit/persistence passed; no browser errors.')
        finally:
            process.terminate()
            process.wait(timeout=15)
            m.engine.dispose()


if __name__ == '__main__':
    main()
