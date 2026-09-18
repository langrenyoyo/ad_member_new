"""Check review All loading under stale requests, changed totals and navigation."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    held, errors = [], []
    mode = 'normal'
    page.on('pageerror', lambda error: errors.append(str(error)))
    def result(route):
        q = parse_qs(urlparse(route.request.url).query)
        base = 1000 if q.get('user_id') == ['2'] else 0
        offset, limit = int(q['offset'][0]), int(q['limit'][0])
        count = 2 if mode == 'shrink' else 0 if mode == 'empty' else 205
        rows = [{'id': base+i, 'user_id': 2 if base else 1, 'status': 0} for i in range(offset, min(count, offset+limit))]
        if mode == 'duplicate' and offset == 200:
            rows[0]['id'] = base
        route.fulfill(json={'total': count, 'items': rows, 'summary': {}})
    def listing(route):
        q = parse_qs(urlparse(route.request.url).query)
        if q['offset'] == ['200']:
            if mode == 'hold':
                held.append(route); return
            if mode == 'changed':
                route.fulfill(json={'total': 204, 'items': []}); return
        result(route)
    page.route('**/api/v1/withdrawals?*', listing)
    page.route('**/api/v1/subsidies?*', listing)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]', '18532306918'); page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    for kind in ['withdrawals', 'subsidies']:
        mode = 'normal'
        page.evaluate('(kind)=>location.hash=kind', kind)
        expect(page.locator('#reviewFilters')).to_have_attribute('data-review-kind', kind)
        mode = 'hold'
        page.locator('#reviewPageSizeMenu summary').click()
        with page.expect_request('**/api/v1/' + kind + '?*offset=200*'):
            page.locator('[data-review-size=All]').click()
        page.fill('#reviewFilters [name=user_id]', '2')
        with page.expect_request('**/api/v1/' + kind + '?*offset=200*'):
            page.locator('#reviewFilters [type=submit]').click()
        page.wait_for_timeout(50)
        assert len(held) == 2
        result(held.pop())
        expect(page.locator('[data-review-cell=id]')).to_have_count(205)
        expect(page.locator('[data-review-cell=id]').first).to_have_text('1000', use_inner_text=True)
        held.pop().fulfill(status=503, json={'detail': 'obsolete batch'})
        page.wait_for_load_state('networkidle')
        expect(page.locator('#reviewError')).to_be_empty()
        for failure in ['changed', 'duplicate']:
            mode = failure; page.locator('#reviewRefresh').click()
            expect(page.locator('#reviewError')).to_contain_text('数据已变化')
            expect(page.locator('[data-review-cell=id]')).to_have_count(205)
            mode = 'normal'; page.locator('#reviewRetry').click()
            expect(page.locator('#reviewError')).to_be_empty()
        page.locator('#reviewPageSizeMenu summary').click()
        page.locator('[data-review-size="10"]').click()
        expect(page.locator('[data-review-cell=id]')).to_have_count(10)
        page.locator('[data-review-page="21"]').click()
        expect(page.locator('[data-review-cell=id]')).to_have_count(5)
        mode = 'shrink'; page.locator('#reviewRefresh').click()
        expect(page.locator('[data-review-cell=id]')).to_have_count(2)
        expect(page.locator('[data-review-cell=id]').first).to_have_text('1000', use_inner_text=True)
        expect(page.locator('.pagination nav')).to_be_hidden()
        mode = 'empty'; page.locator('#reviewRefresh').click()
        expect(page.locator('.pagination')).to_be_hidden()
        mode = 'normal'; page.locator('#reviewRefresh').click()
        expect(page.locator('[data-review-cell=id]')).to_have_count(10)
        mode = 'hold'; page.locator('#reviewPageSizeMenu summary').click()
        with page.expect_request('**/api/v1/' + kind + '?*offset=200*'):
            page.locator('[data-review-size=All]').click()
        page.evaluate('location.hash="dashboard"')
        expect(page.locator('.withdrawal-panel')).to_have_count(0)
        held.pop().fulfill(status=503, json={'detail': 'departed batch'})
        page.wait_for_load_state('networkidle')
        assert page.locator('#reviewError').count() == 0
        page.evaluate('localStorage.setItem("pagesize","10")')
    assert not errors, errors
    browser.close()
print('PASS: both All views reject stale batches, changed totals and duplicates; retry, shrinking/empty lists and navigation')
