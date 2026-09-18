"""Capture review pages and check control containment at desktop/mobile widths."""
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

out = Path('visual-baseline/verified'); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def listing(route):
        q = parse_qs(urlparse(route.request.url).query)
        offset, limit = int(q['offset'][0]), int(q['limit'][0])
        rows = [{'id': 9000+i, 'user_id': 8000+i, 'username': 'Fixture '+str(i), 'status': 0, 'exchange_value': 125,
                 'tx_price': 12.5, 'price': 12, 'game_name': 'Fixture game', 'created_at': '2026-09-16T00:00:00Z'}
                for i in range(offset, min(205, offset+limit))]
        route.fulfill(json={'total': 205, 'items': rows, 'summary': {'paid': 100, 'pending': 50}})
    page.route('**/api/v1/withdrawals?*', listing)
    page.route('**/api/v1/subsidies?*', listing)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]', '18532306918'); page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    for kind in ['withdrawals', 'subsidies']:
        page.evaluate('(kind)=>location.hash=kind', kind)
        expect(page.locator('#reviewFilters')).to_have_attribute('data-review-kind', kind)
        for width, height in [(1920, 1080), (1024, 768), (390, 844)]:
            page.set_viewport_size({'width': width, 'height': height})
            if width <= 640:
                page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right<=1")
            page.locator('#reviewFilters').scroll_into_view_if_needed()
            violations = page.evaluate('''()=>[...document.querySelectorAll('.withdrawal-toolbar>*,.withdrawal-tabs>button,#reviewFilters>label,.pagination nav')].filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,cls:e.className,rect:e.getBoundingClientRect().toJSON()})).filter(e=>e.rect.x<0||e.rect.right>innerWidth+1)''')
            assert not violations, (kind, width, violations)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(out/f'{kind}-{width}.png'), animations='disabled')
            if width <= 640:
                page.locator('#reviewSearchToggle').click()
                page.locator('.withdrawal-panel .pagination').scroll_into_view_if_needed()
                page.screenshot(path=str(out/f'{kind}-{width}-pagination.png'), animations='disabled')
                page.locator('#reviewSearchToggle').click()
    assert not errors, errors
    browser.close()
print('PASS: review filters, tabs, toolbar and pagination fit 1920/1024/390 viewports')
