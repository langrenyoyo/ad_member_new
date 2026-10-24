"""Read-only browser checks against the local demonstration service."""
from pathlib import Path
from playwright.sync_api import sync_playwright

output = Path('artifacts/admin-layout')
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.goto('http://127.0.0.1:8000/')
    page.locator('#loginForm [name=username]').fill('admin')
    page.locator('#loginForm [name=password]').fill('Admin123!')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.app-shell').wait_for(state='visible')
    for width in (1440, 390):
        page.set_viewport_size({'width': width, 'height': 1000})
        for route in ('members', 'risk-whitelist', 'ads', 'agents', 'games', 'withdrawals', 'ad-settings', 'risk-devices'):
            page.goto('http://127.0.0.1:8000/#'+route)
            page.wait_for_timeout(600)
            if route == 'risk-devices':
                game_id=page.evaluate("async()=>{const r=await api('/games?limit=1');return r.items[0].id}")
                page.locator('[data-load] input').fill(str(game_id))
                page.locator('[data-load] button').click()
                page.locator('[data-save]').wait_for()
            page.screenshot(path=str(output / f'{route}-{width}.png'), full_page=True)
            print(route, width, page.evaluate('({viewport:innerWidth,width:document.documentElement.scrollWidth})'))
    browser.close()
