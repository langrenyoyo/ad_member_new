"""Exercise review lookup controls with isolated records and no business writes."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    reads, lookups, held, errors = [], [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def listing(route):
        reads.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total': 1, 'items': [{'id': 1, 'status': 0}], 'summary': {}})

    def lookup(route):
        q = parse_qs(urlparse(route.request.url).query)
        source = urlparse(route.request.url).path.rsplit('/', 1)[-1]
        lookups.append((source, q))
        assert route.request.method == 'GET'
        assert route.request.headers.get('authorization', '').startswith('Bearer ')
        if q.get('id') == ['7999']:
            held.append(route)
            return
        rows = [{'id': 7200 + i, 'name': f'{source} {i:03d} <>&'} for i in range(205)]
        if q.get('id'):
            rows = [row for row in rows if str(row['id']) == q['id'][0]]
        if q.get('q'):
            rows = [row for row in rows if q['q'][0] in row['name']]
        offset = int(q['offset'][0])
        route.fulfill(json={'total': len(rows), 'items': rows[offset:offset + 10]})

    page.route('**/api/v1/withdrawals?*', listing)
    page.route('**/api/v1/subsidies?*', listing)
    page.route('**/api/v1/member-filter-options/**', lookup)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    for kind in ['withdrawals', 'subsidies']:
        page.evaluate('(kind)=>location.hash=kind', kind)
        expect(page.locator('#reviewFilters')).to_have_attribute('data-review-kind', kind)
        for key, source in [('game_id', 'games'), ('agent_id', 'agents')]:
            field = page.locator('[data-review-lookup=' + key + ']')
            field.click()
            expect(page.locator('.sp_result_area:visible li[pkey]')).to_have_count(10)
            field.press('ArrowRight')
            page.locator('.sp_result_area:visible li[pkey="7211"]').click()
            expect(field).to_have_value(source + ' 011 <>&')
            with page.expect_response('**/api/v1/' + kind + '?*'):
                page.locator('#reviewFilters [type=submit]').click()
            assert reads[-1][key] == ['7211']
            expect(field).to_have_value(source + ' 011 <>&')
            field.click()
            field.fill('204')
            field.press('x')
            field.press('Backspace')
            page.locator('.sp_result_area:visible li[pkey="7404"]').click()
            with page.expect_response('**/api/v1/' + kind + '?*'):
                page.locator('#reviewFilters [type=submit]').click()
            assert reads[-1][key] == ['7404']
            expect(field).to_have_value(source + ' 204 <>&')
            field.locator('..').locator('.sp_clear_btn').click()
            page.locator('#reviewFilters [name=username]').click()
            with page.expect_response('**/api/v1/' + kind + '?*'):
                page.locator('#reviewFilters [type=submit]').click()
            assert key not in reads[-1]
        for result in ['success', 'failure']:
            with page.expect_request('**/member-filter-options/games?*id=7999*'):
                page.evaluate('(kind)=>{reviewStates[kind].filters.game_id="7999";renderReviewPage(kind)}', kind)
            field = page.locator('[data-review-lookup=game_id]')
            field.click()
            page.locator('.sp_result_area:visible li[pkey="7200"]').click()
            if result == 'success':
                held.pop().fulfill(json={'total': 1, 'items': [{'id': 7999, 'name': 'Old result'}]})
            else:
                held.pop().fulfill(status=503, json={'detail': 'old failure'})
            page.wait_for_load_state('networkidle')
            expect(field).to_have_value('games 000 <>&')
            expect(page.locator('#reviewFilters [name=game_id]')).to_have_value('7200')
        page.locator('#reviewFilters [type=reset]').click()
        expect(page.locator('[data-review-lookup=game_id]')).to_have_value('')

    page.evaluate('location.hash="withdrawals?agent_id=7200"')
    expect(page.locator('[data-review-lookup=agent_id]')).to_be_disabled()
    expect(page.locator('[data-review-lookup=agent_id]')).to_have_value('agents 000 <>&')
    assert reads[-1]['agent_id'] == ['7200']
    page.locator('[data-review-lookup=game_id]').click()
    expect(page.locator('.sp_result_area:visible li[pkey]')).to_have_count(10)
    assert lookups[-1][1]['agent_id'] == ['7200']
    page.evaluate('location.hash="dashboard"')
    expect(page.locator('.sp_result_area')).to_have_count(0)
    assert not errors, errors
    browser.close()
print('PASS: both review lookups, 205 options, paging/search, authenticated IDs, clear/reset, stale replies, scope and disposal')
