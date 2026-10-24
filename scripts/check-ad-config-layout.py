"""Verify advertisement settings navigation without modifying configuration."""
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path('artifacts/ad-config-layout')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8000/')
    page.locator('#loginForm [name=username]').fill('admin')
    page.locator('#loginForm [name=password]').fill('Admin123!')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('.app-shell').wait_for(state='visible')
    page.goto('http://127.0.0.1:8000/#ad-settings')
    page.locator('#adApplication').wait_for()
    for width in (1440, 390):
        page.set_viewport_size({'width': width, 'height': 1000})
        for tab in ('applications', 'platform', 'reports'):
            page.locator(f'#ad-{tab}-tab').click()
            if tab == 'platform':
                page.locator('.ad-global-keys').wait_for()
                assert page.locator('[name=publisher_key]').input_value() == ''
            assert page.locator('[role=tabpanel]:visible').count() == 1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(out / f'{tab}-{width}.png'), full_page=True)
            print(tab, width, 'OK')
    page.locator('#ad-applications-tab').click()
    field=page.locator('[data-ad-game]:visible [name=app_id]')
    original=field.input_value()
    field.fill('unsaved-layout-check')
    page.locator('#ad-platform-tab').click()
    page.locator('#ad-applications-tab').click()
    assert field.input_value() == 'unsaved-layout-check'
    field.fill(original)
    assert not errors, errors
    print('Unsaved input retained; no JavaScript errors; no configuration writes.')
    browser.close()
