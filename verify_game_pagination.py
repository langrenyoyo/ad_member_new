"""Game history pagination and All mode with isolated, delayed API fixtures."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors, queries, pending = [], [], []
    mode = {'value': 'normal', 'total': 450}
    rows = [dict(id=i, game_id=9300, username=f'fixture-{i}', name='fixture',
                 status=1, coin=i, user_id=i, lottery_price=i, exchange_value=i)
            for i in range(1, 451)]
    page.on('pageerror', lambda error: errors.append(str(error)))

    def api(route):
        url = urlparse(route.request.url)
        if url.path == '/api/auth/login':
            route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}})
            return
        assert route.request.method == 'GET', route.request.url
        if url.path == '/api/v1/games':
            route.fulfill(json={'total': 1, 'items': [{'id': 9300, 'name': 'fixture game'}]})
            return
        if url.path not in ['/api/v1/members', '/api/v1/withdrawals', '/api/v1/games/9300/lottery-records']:
            route.fulfill(json={'total': 0, 'items': []})
            return
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        queries.append((url.path, query))
        if url.path != '/api/v1/games/9300/lottery-records':
            assert query['game_id'] == '9300'
        size, offset = int(query['limit']), int(query['offset'])
        assert 0 < size <= 200 and offset >= 0
        matching = rows[:mode['total']]
        if query.get('username'):
            matching = [row for row in matching if row['username'] == query['username']]
        matching = sorted(matching, key=lambda row: row[query['sort']], reverse=query['order'] == 'desc')
        data = {'total': len(matching), 'items': matching[offset:offset + size]}
        if offset == 200:
            if mode['value'] == 'delay':
                pending.append((route, data))
                return
            if mode['value'] == 'denied':
                route.fulfill(status=403, json={'detail': 'fixture denied'})
                return
            if mode['value'] == 'changed':
                data['total'] += 1
            if mode['value'] == 'empty':
                data['items'] = []
            if mode['value'] == 'duplicate':
                data['items'][0] = matching[0]
        route.fulfill(json=data)

    page.route('**/api/**', api)
    page.goto('http://127.0.0.1:3000/#games')
    page.fill('#loginForm [name=username]', 'fixture')
    page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-game-user="9300"]').click()
    page.locator('[data-tab=four]').click()
    pane = page.locator('#game-user-pane-four')
    pagination = pane.locator('.game-user-pagination')
    pane.locator('[data-member-select]').first.wait_for()

    def settle():
        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')

    def loaded():
        page.wait_for_function("!document.querySelector('#game-user-pane-four .game-user-results').hasAttribute('aria-busy')")
        settle()

    def choose(size):
        pagination.locator('summary').click()
        pagination.locator(f'[data-game-size="{size}"]').click()

    def first_id():
        return pane.locator('[data-member-select]').first.get_attribute('data-member-select')

    pagination.locator('summary').click()
    assert pagination.locator('[data-game-size]').all_text_contents() == ['10', '15', '20', '25', '50', 'All']
    page.keyboard.press('Escape')
    assert not pagination.locator('details').evaluate('el=>el.open')
    assert page.locator('.game-user-dialog').is_visible()
    pagination.locator('[aria-label="\u4e0a\u4e00\u9875"]').click()
    loaded()
    assert first_id() == '10'
    pagination.locator('[aria-label="\u4e0b\u4e00\u9875"]').click()
    loaded()
    assert first_id() == '450'
    jump = pagination.locator('input')
    before = len(queries)
    for value in ('', '0', '-1', '1.5', '46', 'abc'):
        jump.fill(value)
        jump.press('Enter')
    settle()
    assert len(queries) == before
    jump.fill('20')
    jump.press('Enter')
    loaded()
    assert first_id() == '260'
    assert pagination.locator('[aria-current=page]').inner_text() == '20'
    choose(25)
    loaded()
    assert pane.locator('[data-member-select]').count() == 25 and first_id() == '450'

    # Batch failures preserve the last complete table, selection and page label.
    pane.locator('[data-member-select]').first.check()
    for failure in ('changed', 'empty', 'duplicate', 'denied'):
        mode['value'] = failure
        choose('All')
        loaded()
        assert pane.locator('[role=alert]').inner_text()
        assert pane.locator('[data-member-select]').count() == 25
        assert pane.locator('[data-member-select]').first.is_checked()
        assert pagination.locator('summary').inner_text().strip() == '25'
        assert pagination.locator('[aria-current=page]').inner_text() == '1'
    mode['value'] = 'normal'
    before = len(queries)
    pane.locator('[data-action=refresh]').click()
    loaded()
    assert [q['offset'] for path, q in queries[before:]] == ['0', '200', '400']
    assert pane.locator('[data-member-select]').count() == 450
    assert not pane.locator('[data-member-select]').first.is_checked()
    assert pagination.locator('nav').is_hidden()
    assert '450' in pagination.inner_text()
    pane.locator('[data-sort=coin]').click()
    loaded()
    pane.locator('[data-sort=coin]').click()
    loaded()
    assert first_id() == '1'

    # Pending All reads cannot overwrite a newer page-size request.
    choose(10)
    loaded()
    mode['value'] = 'delay'
    with page.expect_request(lambda request: '/members?' in request.url and 'offset=200' in request.url):
        choose('All')
    settle()
    assert pending
    late, response = pending.pop()
    choose(15)
    loaded()
    before = len(queries)
    late.fulfill(json=response)
    settle()
    assert pane.locator('[data-member-select]').count() == 15 and len(queries) == before
    assert pagination.locator('summary').inner_text().strip() == '15'
    mode['value'] = 'normal'

    # All honors the active filter and survives card/table view changes.
    choose('All')
    loaded()
    pane.locator('[data-action=search]').click()
    pane.locator('[name=username]').fill('fixture-17')
    pane.locator('form [type=submit]').click()
    loaded()
    assert pane.locator('[data-member-select]').count() == 1 and first_id() == '17'
    assert pagination.locator('.game-page-size').is_hidden()
    pane.locator('[data-action=cards]').click()
    assert pane.locator('.game-user-cards article').count() == 1
    pane.locator('[data-action=cards]').click()
    pane.locator('form [type=reset]').click()
    loaded()
    assert pane.locator('[data-member-select]').count() == 450
    choose(10)
    loaded()
    pagination.locator('input').fill('45')
    pagination.locator('[data-game-jump]').click()
    loaded()
    mode['total'] = 21
    pane.locator('[data-action=refresh]').click()
    loaded()
    assert pagination.locator('[aria-current=page]').inner_text() == '3'
    assert first_id() == '21'
    pagination.locator('summary').click()
    assert pagination.locator('[data-game-size]').all_text_contents() == ['10', '15', '20', '25']
    page.keyboard.press('Escape')
    mode['total'] = 450
    pane.locator('[data-action=refresh]').click()
    loaded()
    page.set_viewport_size({'width': 390, 'height': 844})
    pagination.scroll_into_view_if_needed()
    assert pagination.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    out = Path('visual-baseline/verified')
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / 'game-pagination-mobile.png'))
    page.set_viewport_size({'width': 1920, 'height': 1080})

    # The common pagination supports the other history tabs as well.
    choose('All')
    loaded()
    page.locator('[data-tab=third]').click()
    third = page.locator('#game-user-pane-third')
    third.locator('tbody tr').first.wait_for()
    page.wait_for_function("document.querySelectorAll('#game-user-pane-third tbody tr').length===450")
    assert queries[-1][0] == '/api/v1/withdrawals'
    page.locator('[data-tab=four]').click()
    choose(10)
    loaded()
    mode['value'] = 'delay'
    with page.expect_request(lambda request: '/members?' in request.url and 'offset=200' in request.url):
        choose('All')
    settle()
    assert pending
    late, response = pending.pop()
    page.locator('[data-dialog-close]').click()
    page.locator('.game-user-dialog').wait_for(state='detached')
    before = len(queries)
    late.fulfill(json=response)
    settle()
    assert len(queries) == before and page.locator('.game-user-dialog').count() == 0
    assert not errors, errors
    browser.close()

print('Game pagination: reference sizes/loop/jump, All batches, filter/sort, failures, selection, stale responses, count shrink, mobile and parent cleanup passed')
