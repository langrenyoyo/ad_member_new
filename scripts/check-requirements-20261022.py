"""Read-only local browser checks for the October 22 requirement screens."""
from pathlib import Path
from playwright.sync_api import sync_playwright

output = Path('artifacts/requirements-20261022')
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8000/')
    page.locator('#loginForm [name=username]').fill('admin')
    page.locator('#loginForm [name=password]').fill('Admin123!')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.app-shell').wait_for(state='visible')
    for width in (1440, 390):
        page.set_viewport_size({'width': width, 'height': 1000})
        for route in ('ads', 'withdrawals', 'risk-history', 'members', 'risk-whitelist', 'risk-devices'):
            page.goto('http://127.0.0.1:8000/#'+route)
            page.wait_for_timeout(800)
            if route == 'risk-devices':
                game=page.evaluate("async()=>{const r=await api('/games?limit=1');return r.items[0].id}")
                host=page.locator('#memberPolicyHost')
                host.locator('[data-load] input').fill(str(game))
                host.locator('[data-load] button').click()
                host.locator('[data-save]').wait_for()
                assert host.locator('[name=whitelist_risk_exempt]').count()==0
                assert '未绑定老账号须补绑上级' in host.inner_text()
            page.screenshot(path=str(output/f'{route}-{width}.png'), full_page=True)
            print(route, width, page.locator('#content').inner_text()[:80])
    assert not errors, errors
    browser.close()
