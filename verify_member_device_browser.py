"""Device actions and nested APP details against isolated browser fixtures."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1536, 'height': 900})
    errors, queries, writes = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    device = dict(device_id='device-fixture', imei='imei-fixture', device_id_ban=0, imei_id_ban=0,
                  android_version='14', model='<img src=x onerror=alert(1)>', app_version='2.7',
                  ip_address='fixture region', sim_info='fixture SIM', risk_flag=0, usb_debugging=1, rooted=0)
    summary = dict(coin=123, today_lottery_coin=45, today_average_coin=9,
                   total_clicks=200, today_clicks=8, today_failed=2, device=device)
    mode = {'ban_error': 0, 'list_error': False, 'usage': 'normal', 'remove_imei': False}
    usage_rows = [dict(id=i, app_name='<b>fixture</b>', count=2, package_name='test.' + 'a' * 90,
                       duration_seconds=75, first_used_at='2026-09-17T04:00:00Z',
                       last_used_at='2026-09-17T05:00:00Z') for i in range(203)]

    def handle(route):
        parsed = urlparse(route.request.url)
        path = parsed.path
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        queries.append((path, query))
        if path == '/api/auth/login':
            route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}})
        elif path.endswith('/device-ban'):
            assert path == '/api/v1/members/42/device-ban'
            assert route.request.method == 'PATCH'
            body = route.request.post_data_json
            writes.append(body)
            if mode['ban_error']:
                route.fulfill(status=mode['ban_error'], json={'detail': 'fixture denied or stale'})
                return
            field = 'imei' if body['target'] == 'imei' else 'device_id'
            assert body['expected_identifier'] == device[field]
            device['imei_id_ban' if body['target'] == 'imei' else 'device_id_ban'] = int(body['banned'])
            route.fulfill(json=summary)
            if mode['remove_imei']:
                device['imei'] = ''
                mode['remove_imei'] = False
        else:
            assert route.request.method == 'GET', (path, route.request.method)
            if path.endswith('/lottery-records'):
                if mode['list_error']:
                    mode['list_error'] = False
                    route.fulfill(status=503, json={'detail': 'fixture refresh failed'})
                else:
                    route.fulfill(json={'total': 0, 'items': [], 'member_summary': summary})
            elif path.endswith('/app-usage'):
                assert path == '/api/v1/members/42/app-usage'
                offset, limit = int(query['offset']), int(query['limit'])
                if mode['usage'] == 'error':
                    route.fulfill(status=403, json={'detail': 'fixture usage denied'})
                    return
                rows = [] if mode['usage'] == 'empty' else usage_rows[offset:offset + limit]
                total = 0 if mode['usage'] == 'empty' else len(usage_rows)
                if offset and mode['usage'] == 'duplicate':
                    rows = [usage_rows[0], *rows[1:]]
                if offset and mode['usage'] == 'changed':
                    total += 1
                route.fulfill(json={'total': total, 'items': rows})
            else:
                route.fulfill(json={'total': 0, 'items': []})

    page.route('**/api/**', handle)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]', 'fixture')
    page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.evaluate("openMemberBehavior(42,237,'single')")
    parent = page.locator('.member-behavior-dialog')
    pane = parent.locator('#behavior-pane-lottery')
    panel = pane.locator('.behavior-lottery-summary')
    panel.wait_for()
    assert panel.locator('strong').all_text_contents() == ['123', '45', '9', '200', '8', '2']
    assert panel.locator('img').count() == 0
    assert '<img src=x' in panel.inner_text()
    assert 'USB调试：是' in panel.inner_text() and '是否越狱：否' in panel.inner_text()
    ban = pane.locator('[data-device-ban=device]')
    imei = pane.locator('[data-device-ban=imei]')

    def settled():
        page.wait_for_function("!document.querySelector('#behavior-pane-lottery').behaviorDeviceSaving")

    # A double click while saving must issue just one write and lock both targets.
    page.evaluate("""()=>{
      window.originalApi=api;
      api=(path,options)=>path.endsWith('/device-ban')?new Promise(resolve=>{
        window.finishBan=()=>resolve(originalApi(path,options));
      }):originalApi(path,options);
    }""")
    ban.evaluate('el=>{el.click();el.click();}')
    assert ban.is_disabled() and imei.is_disabled()
    page.evaluate('finishBan();api=originalApi')
    settled()
    assert len(writes) == 1 and writes[0] == dict(target='device', banned=True, expected_identifier='device-fixture')
    assert ban.inner_text() == '解禁' and imei.inner_text() == '封禁'
    imei.click(); settled()
    assert writes[-1]['target'] == 'imei' and imei.inner_text() == '解禁'
    for status in (403, 409):
        mode['ban_error'] = status
        ban.click(); settled()
        assert ban.inner_text() == '解禁' and not ban.is_disabled()
        assert 'fixture denied' in pane.locator('[role=alert]').inner_text()
    mode['ban_error'] = 0
    mode['list_error'] = True
    ban.click(); settled()
    assert ban.inner_text() == '封禁'
    assert 'fixture refresh failed' in pane.locator('[role=alert]').inner_text()
    mode['remove_imei'] = True
    ban.click(); settled()
    assert ban.inner_text() == '解禁' and imei.is_disabled()

    def open_usage():
        pane.locator('[data-app-usage]').click()
        return page.locator('.member-app-usage-dialog')

    detail = open_usage()
    page.wait_for_function("document.querySelectorAll('.member-app-usage-dialog tbody tr').length===203")
    assert detail.locator('thead th').all_text_contents() == ['APP名称', '次数', '包名', '使用时间', '当天第一次使用时间', '最后一次使用时间']
    assert detail.locator('tbody tr').first.locator('td').all_text_contents() == [
        '<b>fixture</b>', '2', 'test.' + 'a' * 90, '75秒', '2026-09-17 12:00:00', '2026-09-17 13:00:00']
    assert detail.locator('tbody b').count() == 0
    usage_queries = [query for path, query in queries if path.endswith('/app-usage')]
    assert [query['offset'] for query in usage_queries] == ['0', '200']
    assert all(query['game_id'] == '237' and query['limit'] == '200' for query in usage_queries)
    assert detail.get_attribute('aria-label') == 'APP应用'
    original = detail.bounding_box()
    assert original['width'] == 800 and original['height'] == 600
    header = detail.locator('header').bounding_box()
    page.mouse.move(header['x'] + 80, header['y'] + 20)
    page.mouse.down(); page.mouse.move(header['x'] + 120, header['y'] + 40); page.mouse.up()
    moved = detail.bounding_box()
    assert abs(moved['x'] - original['x'] - 40) < 1
    detail.locator('[data-usage-maximize]').click()
    assert detail.bounding_box()['width'] == 1536 and detail.bounding_box()['height'] == 900
    detail.locator('[data-usage-maximize]').click()
    assert detail.bounding_box()['width'] == 800
    detail.locator('[data-usage-minimize]').click()
    assert detail.bounding_box()['width'] == 180 and detail.bounding_box()['height'] == 45
    assert detail.locator('main').is_hidden()
    assert detail.evaluate('el=>el.parentElement.classList.contains("member-behavior-dialog")')
    parent.locator('[data-behavior-tab=lottery]').click()
    detail.locator('[data-usage-maximize]').click()
    assert detail.evaluate('el=>el.matches(":modal")')
    assert detail.locator('tbody tr').count() == 203
    page.keyboard.press('Escape'); detail.wait_for(state='detached')
    assert parent.is_visible()
    for behavior in ('error', 'duplicate', 'changed'):
        mode['usage'] = behavior
        detail = open_usage()
        detail.locator('[role=alert]').wait_for()
        assert detail.locator('table').count() == 0
        mode['usage'] = 'empty'
        detail.locator('[data-retry]').click()
        detail.get_by_text('没有找到匹配的记录').wait_for()
        detail.locator('[aria-label=关闭]').click(); detail.wait_for(state='detached')

    output = Path('visual-baseline/verified')
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / 'member-device-desktop.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert parent.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    assert panel.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    for box in panel.locator(':scope>div').all():
        assert box.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path=str(output / 'member-device-mobile.png'))
    mode['usage'] = 'normal'
    detail = open_usage()
    detail.locator('table').wait_for()
    assert detail.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path=str(output / 'member-app-usage-mobile.png'))
    page.evaluate("document.querySelector('.member-behavior-dialog').close()")
    parent.wait_for(state='detached'); detail.wait_for(state='detached')

    # Ignore abort in this fixture so late completions exercise the UI's own guards.
    page.evaluate("""()=>{
      api=(path,options)=>path.includes('/app-usage?')?new Promise(resolve=>{
        window.usageSignal=options.signal;window.finishUsage=resolve;
      }):originalApi(path,options);
      openMemberBehavior(42,237,'multiple');
    }""")
    panel.wait_for()
    detail = open_usage()
    page.wait_for_function('window.finishUsage!==undefined')
    detail.locator('[data-usage-minimize]').click()
    assert not page.evaluate('usageSignal.aborted')
    page.evaluate("document.querySelector('.member-behavior-dialog').close()")
    detail.wait_for(state='detached')
    page.wait_for_function('usageSignal.aborted')
    page.evaluate('finishUsage({total:0,items:[]});api=originalApi')
    assert page.locator('.member-app-usage-dialog').count() == 0

    page.evaluate("""()=>{
      api=(path,options)=>path.endsWith('/device-ban')?new Promise(resolve=>window.finishClosedBan=resolve):originalApi(path,options);
      openMemberBehavior(42,237,'multiple');
    }""")
    panel.wait_for(); ban.click()
    page.evaluate("document.querySelector('.member-behavior-dialog').close()")
    parent.wait_for(state='detached')
    before = [query for query in queries if query[0].endswith('/lottery-records')]
    page.evaluate('finishClosedBan({device:{}});api=originalApi')
    assert [query for query in queries if query[0].endswith('/lottery-records')] == before
    page.evaluate("openMemberBehavior(42,237,'multiple')")
    panel.wait_for(); detail = open_usage(); detail.locator('table').wait_for()
    assert 'game_id' not in [query for path, query in queries if path.endswith('/app-usage')][-1]
    page.evaluate("location.hash='games'")
    parent.wait_for(state='detached'); detail.wait_for(state='detached')
    assert not errors, errors
    browser.close()

print('Member devices: independent bans, locking, 403/409, saved state after refresh failure, missing identifier, APP batches/retry/escaping, mobile and late completion cleanup passed')
