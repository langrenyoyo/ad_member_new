from playwright.sync_api import sync_playwright
from playwright.sync_api import expect

routes = ['dashboard', 'members', 'ads', 'agents', 'games', 'withdrawals', 'subsidies',
          'coin-logs', 'risk-whitelist', 'risk-history', 'risk-devices', 'profile', 'book']
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('form=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    for route in routes:
        page.goto('http://127.0.0.1:3000/#' + route, wait_until='networkidle')
        page.wait_for_function("document.querySelector('#content')?.getAttribute('aria-busy') !== 'true'")
        expect(page.locator('#content > *').first).to_be_visible()
        expect(page.locator('#content .error-state')).to_have_count(0)
        messages = [text.strip() for text in page.locator('#content [role=alert]').all_inner_texts() if text.strip()]
        assert not messages, (route, messages)
        print(route, 'PASS')
    assert not errors, errors
    browser.close()
