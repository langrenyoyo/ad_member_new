"""Statistics failures, late responses and chart cleanup with browser-only fixtures."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    state = {'api_fail': True, 'map_attempts': 0}

    def fixture(route):
        if route.request.url.endswith('/auth/login'):
            route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}})
        elif route.request.url.endswith('/statistics'):
            if state['api_fail']:
                route.fulfill(status=503, json={'detail': 'fixture statistics unavailable'})
            else:
                route.fulfill(json={'total_income': 7, 'total_members': 12, 'mapdata': [],
                                    'mapdata1': [], 'mapdata2': [], 'metric_series': [], 'registration_series': []})
        else:
            assert route.request.method == 'GET'
            route.fulfill(json={'total': 0, 'items': []})

    def map_fixture(route):
        state['map_attempts'] += 1
        if state['map_attempts'] == 1:
            route.abort()
        elif state['map_attempts'] == 2:
            route.fulfill(body='/* successful HTTP response but no registered map */', content_type='application/javascript')
        else:
            route.continue_()

    page.route('**/api/**', fixture)
    page.route('**/vendor/china-map.js', map_fixture)
    page.goto('http://127.0.0.1:3000/#games')
    page.fill('#loginForm [name=username]', 'fixture')
    page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.app-shell').wait_for(state='visible')
    page.evaluate('openGameProfitData(42)')
    alert = page.locator('#game-user-pane-seven [role=alert]')
    alert.wait_for()
    assert 'fixture statistics unavailable' in alert.inner_text()
    state['api_fail'] = False
    page.get_by_role('button', name='重试', exact=True).click()
    page.wait_for_function("document.querySelector('#game-user-pane-seven [role=alert]')?.textContent==='组件加载失败'")
    page.get_by_role('button', name='重试', exact=True).click()
    page.wait_for_function("document.querySelector('#game-user-pane-seven [role=alert]')?.textContent==='地图加载失败'")
    page.get_by_role('button', name='重试', exact=True).click()
    page.wait_for_function("document.querySelectorAll('[data-stat-chart] canvas').length===4")
    assert state['map_attempts'] == 3
    assert page.locator('[data-stat-chart=region-map]').evaluate("el=>echarts.getInstanceByDom(el).getOption().visualMap[0].max") == 5
    assert '更新日期' not in page.locator('.game-stat-cards').inner_text()

    page.evaluate('''()=>{
        window.fixtureOriginalApi=api;
        window.fixturePending=[];
        api=(url,options)=>url.endsWith('/statistics')?new Promise(resolve=>fixturePending.push({resolve,signal:options.signal})):fixtureOriginalApi(url,options);
        window.fixtureCharts=Array.from(document.querySelectorAll('[data-stat-chart]'),el=>echarts.getInstanceByDom(el));
    }''')
    page.locator('[data-tab=first]').click()
    assert page.evaluate('fixtureCharts.every(chart=>chart.isDisposed())')
    page.locator('[data-tab=seven]').click()
    page.wait_for_function('fixturePending.length===1')
    page.locator('[data-tab=first]').click()
    assert page.evaluate('fixturePending[0].signal.aborted')
    page.evaluate('fixturePending[0].resolve({total_income:999})')
    page.wait_for_timeout(150)
    assert page.locator('[data-stat-chart]').count() == 0
    page.locator('[data-tab=seven]').click()
    page.wait_for_function('fixturePending.length===2')
    page.locator('[data-dialog-close]').click()
    page.locator('.game-user-dialog').wait_for(state='detached')
    assert page.evaluate('fixturePending[1].signal.aborted')
    page.evaluate('fixturePending[1].resolve({total_income:999})')
    page.evaluate('()=>{api=fixtureOriginalApi;}')
    page.evaluate('openGameProfitData(43)')
    page.wait_for_function("document.querySelectorAll('[data-stat-chart] canvas').length===4")
    assert page.locator('.game-stat-cards strong').first.inner_text() == '¥7.00'
    page.evaluate("()=>{window.fixtureCharts=Array.from(document.querySelectorAll('[data-stat-chart]'),el=>echarts.getInstanceByDom(el));location.hash='members';}")
    page.locator('.game-user-dialog').wait_for(state='detached')
    assert page.evaluate('fixtureCharts.every(chart=>chart.isDisposed())')
    assert not errors, errors
    browser.close()
print('Statistics: API/map retry, empty data, stale responses, abort on switch/close and route cleanup passed')
