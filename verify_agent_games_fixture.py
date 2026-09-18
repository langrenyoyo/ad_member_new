"""Exercise scoped game loading and paging with browser-only synthetic records."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

rows = [dict(id=9000+i, agent_id=9000, name=f'游戏 {i}', status=i % 2,
             game_type=i % 3, game_ad_status=1, game_lottery_num=i / 10,
             created_at='2026-09-16T00:00:00Z') for i in range(25)]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('agent-dashboard-id','9000')")
    page.route('**/api/v1/agents/9000', lambda route: route.fulfill(json={'id':9000,'name':'对照主体'}))
    requests = []
    def games(route):
        query = parse_qs(urlparse(route.request.url).query)
        assert query['agent_id'] == ['9000'], query
        requests.append(query)
        filtered = rows if not query.get('name') else []
        offset, limit = int(query['offset'][0]), int(query['limit'][0])
        route.fulfill(json={'total':len(filtered),'items':filtered[offset:offset+limit]})
    page.route('**/api/v1/games?*', games)
    page.goto('http://127.0.0.1:3000/#agent-games')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-game-edit]').first.wait_for()
    assert page.locator('[data-game-edit]').count() == 20
    page.locator('#agentGameNext').click()
    page.locator('[data-game-edit="9024"]').wait_for()
    assert page.locator('[data-game-edit]').count() == 5
    assert page.locator('#agentGameNext').is_disabled()
    page.locator('[data-agent-game-sort="created_at"]').click()
    page.locator('[data-game-edit="9000"]').wait_for()
    assert requests[-1]['offset'] == ['0'] and requests[-1]['sort'] == ['created_at']
    page.fill('#agentGameFilters [name=name]', '不存在的游戏')
    page.select_option('#agentGameFilters [name=ad_status]', '0')
    page.locator('#agentGameFilters [type=submit]').click()
    page.get_by_text('没有找到匹配的记录', exact=True).wait_for()
    assert requests[-1]['ad_status'] == ['0']
    assert page.locator('.ads-table tbody td').get_attribute('colspan') == str(page.locator('.ads-table thead th').count())
    page.locator('#agentGameFilters [type=reset]').click()
    page.locator('[data-game-edit="9000"]').wait_for()
    assert 'name' not in requests[-1] and 'ad_status' not in requests[-1]
    assert not errors, errors
    browser.close()
print('Scoped games: 25 records, pagination, sort reset, disabled filter and empty state passed')
