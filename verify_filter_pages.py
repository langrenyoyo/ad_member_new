"""Check restored lookup dependencies on ledger and risk pages without writes."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors, reads = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def listing(route):
        reads.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total': 1, 'items': [{'id': 1, 'user_id': 1, 'username': 'Fixture', 'status': 1, 'is_white': 1}], 'summary': {'change': 0}})
    def lookup(route):
        q = parse_qs(urlparse(route.request.url).query)
        rows = [{'id': 7200+i, 'name': f'Fixture {i:03d} <>&'} for i in range(205)]
        if q.get('id'): rows = [row for row in rows if str(row['id']) == q['id'][0]]
        if q.get('q'): rows = [row for row in rows if q['q'][0] in row['name']]
        offset = int(q['offset'][0])
        assert route.request.headers.get('authorization', '').startswith('Bearer ')
        route.fulfill(json={'total': len(rows), 'items': rows[offset:offset+10]})
    for endpoint in ['coin-logs', 'risk/whitelist', 'risk/history']:
        page.route('**/api/v1/' + endpoint + '?*', listing)
    page.route('**/api/v1/member-filter-options/**', lookup)
    page.goto('http://127.0.0.1:3000/#coin-logs')
    page.fill('#loginForm [name=username]', '18532306918'); page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    for route, form_id, endpoint in [('coin-logs', 'coinFilters', 'coin-logs'), ('risk-whitelist', 'whitelistFilters', 'risk/whitelist'), ('risk-history', 'riskHistoryFilters', 'risk/history')]:
        page.evaluate('(route)=>location.hash=route', route)
        form = page.locator('#'+form_id)
        form.wait_for(state='attached')
        if route == 'risk-whitelist': page.locator('#whitelistSearch').click()
        expect(form).to_be_visible()
        for key in ['game_id', 'agent_id']:
            field = form.locator('[data-filter-lookup='+key+']')
            field.click()
            expect(page.locator('.sp_result_area:visible li[pkey]')).to_have_count(10)
            field.press('ArrowRight')
            page.locator('.sp_result_area:visible li[pkey="7211"]').click()
            expect(field).to_have_value('Fixture 011 <>&')
            with page.expect_response('**/api/v1/'+endpoint+'?*'):
                form.locator('[type=submit]').click()
            assert reads[-1][key] == ['7211']
            field.click(); field.fill('204'); field.press('x'); field.press('Backspace')
            page.locator('.sp_result_area:visible li[pkey="7404"]').click()
            with page.expect_response('**/api/v1/'+endpoint+'?*'):
                form.locator('[type=submit]').click()
            assert reads[-1][key] == ['7404']
            field.locator('..').locator('.sp_clear_btn').click()
            form.locator('[name=username]').click()
            with page.expect_response('**/api/v1/'+endpoint+'?*'):
                form.locator('[type=submit]').click()
            assert key not in reads[-1]
        form.locator('[type=reset]').click()
        expect(form.locator('[data-filter-lookup=game_id]')).to_have_value('')
        expect(page.locator('.error-state')).to_have_count(0)
        print(route, 'PASS')
    page.evaluate('location.hash="dashboard"')
    expect(page.locator('.sp_result_area')).to_have_count(0)
    assert not errors, errors
    browser.close()
