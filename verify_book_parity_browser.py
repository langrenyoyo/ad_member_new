"""Tutorial interactions with isolated API responses; no business writes."""
import csv
import io
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

rows = [{'id': i+1, 'name': 'Fixture <>& '+str(i),
    'created_at': (datetime(2040, 1, 1, tzinfo=timezone.utc)+timedelta(minutes=i % 3)).isoformat(),
    'updated_at': (datetime(2040, 1, 2, tzinfo=timezone.utc)+timedelta(minutes=i % 2)).isoformat()} for i in range(225)]
content = Path('visual-baseline/fixtures/book/fixture-content.html').read_text(encoding='utf-8')
content += '<script>parent.window.tutorialExecuted=true</script><img src="/assets/img/avatar.png" onload="parent.window.tutorialExecuted=true"><a href="javascript:alert(1)">Bad link</a><form><input name="bad"></form>'
reads = []; held = []; errors = []; details = []; mode = {'hold': None, 'fail': None, 'drift': False}
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda error: errors.append(str(error)))
    def fixture(route):
        request = route.request; url = urlparse(request.url); path = url.path.removeprefix('/api/').removeprefix('v1/'); q = parse_qs(url.query)
        if path == 'auth/login': route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}}); return
        assert request.method == 'GET', request.url
        kind = 'list' if path == 'tutorials' else 'detail' if path.startswith('tutorials/') else None
        if kind == 'list': reads.append(q)
        if kind == 'detail': details.append(path)
        if kind and mode['hold'] == kind: held.append(route); return
        if kind and mode['fail'] == kind: route.fulfill(status=503, json={'detail': 'fixture unavailable'}); return
        if kind == 'detail': route.fulfill(json={**rows[int(path.split('/')[-1])-1], 'content': content}); return
        if kind == 'list':
            items = list(rows)
            for field in ['created', 'updated']:
                for suffix, op in [('from', lambda a, b: a >= b), ('to', lambda a, b: a <= b)]:
                    if field+'_'+suffix in q:
                        boundary = datetime.fromisoformat(q[field+'_'+suffix][0])
                        items = [row for row in items if op(datetime.fromisoformat(row[field+'_at']), boundary)]
            items.sort(key=lambda r: r['id'], reverse=True)
            items.sort(key=lambda r: r[q.get('sort', ['id'])[0]], reverse=q.get('order', ['desc'])[0] == 'desc')
            offset = int(q.get('offset', ['0'])[0]); limit = int(q.get('limit', ['10'])[0])
            route.fulfill(json={'items': items[offset:offset+limit], 'total': len(items)+(1 if offset and mode['drift'] else 0)}); return
        route.fulfill(json={'items': [], 'total': 0})
    page.route('**/api/**', fixture); page.goto('http://127.0.0.1:3000/#book')
    page.fill('#loginForm [name=username]', 'fixture'); page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    form = page.locator('#tutorialFilters'); table = page.locator('#tutorialList'); error = page.locator('#tutorialError')
    def ready(count=10):
        page.wait_for_function('n=>document.querySelector("#tutorialList tbody")?.rows.length===n&&!document.querySelector("#tutorialList").hasAttribute("aria-busy")', arg=count)
        assert error.inner_text() == '', error.inner_text()
    def submit(): form.evaluate('f=>f.requestSubmit()')
    def reset(): form.locator('[type=reset]').click(); ready()
    def close_all(): page.locator('.tutorial-dialog').evaluate_all('nodes=>nodes.forEach(n=>n.close())'); page.locator('.tutorial-dialog').wait_for(state='detached')
    def opened(index=0):
        dialog = page.locator('.tutorial-dialog').nth(index)
        frame = dialog.frame_locator('iframe'); frame.locator('.tutorial-content').wait_for()
        return dialog, frame
    ready(); assert not form.is_visible() and table.locator('th').count() == 5
    assert reads[-1] == {'limit': ['10'], 'offset': ['0'], 'sort': ['id'], 'order': ['desc']}
    assert not page.locator('#tutorialHost input[type=search]').count()
    # Row and header selection, selected/full exports and reference field exclusion.
    table.locator('td[data-field=name]').first.click(); expect(table.locator('[data-tutorial-select]').first).to_be_checked()
    expect(table.locator('[data-tutorial-all]')).to_have_js_property('indeterminate', True)
    for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download: page.locator('[data-export='+kind+']').click()
        data = Path(download.value.path()).read_bytes(); assert b'Fixture' in data and b'<button' not in data
        if kind == 'json':
            result = json.loads(data); assert len(result['data']) == 1 and result['header'][0] == ['Id', '标题', '创建时间']
        if kind == 'xml': assert 'Fixture <>& 224' in ''.join(ET.fromstring(data).itertext())
    table.locator('[data-tutorial-all]').check(); assert table.locator('[data-tutorial-select]:checked').count() == 10
    table.locator('[data-tutorial-all]').uncheck(); assert not table.locator('[data-tutorial-select]:checked').count()
    page.locator('#tutorialPagination [aria-label="上一页"]').click(); ready(5); assert reads[-1]['offset'] == ['220']
    page.locator('#tutorialPagination [aria-label="下一页"]').click(); ready()
    page.locator('#tutorialPagination input').fill('5'); page.locator('[data-game-jump]').click(); ready(); assert reads[-1]['offset'] == ['40']
    page.locator('.game-user-columns summary').click(); page.locator('[data-column=updated_at]').check(); page.locator('.game-user-columns summary').click()
    for key in ['created_at', 'updated_at']:
        for order in ['desc', 'asc']:
            table.locator('[data-sort='+key+']').click(); ready(); assert reads[-1]['sort'] == [key] and reads[-1]['order'] == [order] and reads[-1]['offset'] == ['0']
    page.locator('#tutorialSearch').click(); expect(form).to_be_visible()
    form.locator('[name=created_range]').fill('2040-01-01 08:01:00 - 2040-01-01 08:01:00')
    form.locator('[name=updated_range]').fill('2040-01-02 08:01:00 - 2040-01-02 08:01:00'); submit(); ready()
    assert reads[-1]['created_from'] == ['2040-01-01T00:01:00.000Z']
    assert reads[-1]['updated_from'] == ['2040-01-02T00:01:00.000Z']
    page.locator('#tutorialRefresh').click(); ready(); assert 'created_from' in reads[-1]
    count = len(reads); form.locator('[name=created_range]').fill('2040-02-30 00:00:00 - 2040-03-01 00:00:00'); submit()
    expect(error).to_contain_text('时间范围无效'); assert len(reads) == count; reset()
    form.locator('[name=created_range]').click(); page.locator('.daterangepicker:visible').wait_for(); page.locator('#tutorialSearch').click()
    page.locator('#tutorialPagination .game-page-size summary').click(); page.locator('[data-game-size=All]').click(); ready(225)
    assert reads[-2]['limit'] == ['200'] and reads[-1]['offset'] == ['200']
    page.locator('#tutorialSearch').click()
    form.locator('[name=created_range]').fill('2050-01-01 00:00:00 - 2050-01-02 00:00:00'); submit(); ready(1)
    expect(table).to_contain_text('没有找到匹配的记录'); expect(page.locator('#tutorialPagination')).not_to_be_visible()
    form.locator('[type=reset]').click(); ready(225); page.locator('#tutorialSearch').click()
    for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download: page.locator('[data-export='+kind+']').click()
        data = Path(download.value.path()).read_bytes()
        if kind == 'json': assert len(json.loads(data)['data']) == 225
        if kind == 'csv': assert len(list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))) == 226
        if kind == 'xml': assert 'Fixture <>& 0' in ''.join(ET.fromstring(data).itertext())
    # Rich text uses a sandboxed document, preserving styles and raster images.
    page.locator('[data-tutorial]').first.click(); dialog, frame = opened()
    assert dialog.bounding_box()['width'] == 800 and dialog.bounding_box()['height'] == 600
    expect(frame.locator('strong')).to_have_text('Bold fixture'); expect(frame.locator('p').first).to_have_css('font-size', '24px')
    assert not frame.locator('script,form,input,[onload],a[href^="javascript:"]').count()
    assert page.evaluate('window.tutorialExecuted') is None
    assert 'allow-scripts' not in dialog.locator('iframe').get_attribute('sandbox')
    frame.locator('img').first.evaluate('async n=>{await n.decode();if(n.naturalWidth===0)throw Error("blank image")}')
    expect(frame.locator('a[href="https://example.com/"]')).to_have_attribute('rel', 'noopener noreferrer')
    # A second independent window leaves the background list usable; Escape closes only the top window.
    page.locator('[data-tutorial]').nth(1).click(); second, _ = opened(1); assert page.locator('.tutorial-dialog').count() == 2
    page.keyboard.press('Escape'); expect(page.locator('.tutorial-dialog')).to_have_count(1)
    page.locator('[data-tutorial]').nth(1).click(); second, second_frame = opened(1)
    second_frame.locator('p').first.click(); page.keyboard.press('Escape'); expect(page.locator('.tutorial-dialog')).to_have_count(1)
    before = dialog.bounding_box(); header = dialog.locator('header').bounding_box()
    page.mouse.move(header['x']+50, header['y']+20); page.mouse.down(); page.mouse.move(header['x']+90, header['y']+50); page.mouse.up()
    after = dialog.bounding_box(); assert after['x'] > before['x'] and after['y'] > before['y']
    dialog.locator('[data-tutorial-maximize]').click(); assert dialog.bounding_box()['width'] == 1920
    dialog.locator('[data-tutorial-maximize]').click(); assert dialog.bounding_box()['width'] == 800
    dialog.locator('[data-tutorial-minimize]').click(); expect(dialog).to_have_class('tutorial-dialog minimized')
    assert dialog.bounding_box()['height'] == 45 and not dialog.locator('main').is_visible()
    page.locator('[data-tutorial]').nth(1).click(); second, _ = opened(1)
    second.locator('[data-tutorial-minimize]').click()
    assert dialog.bounding_box()['x'] == 0 and second.bounding_box()['x'] == 181
    page.set_viewport_size({'width': 320, 'height': 844})
    page.wait_for_function('[...document.querySelectorAll(".tutorial-dialog.minimized")].every(n=>n.getBoundingClientRect().right<=innerWidth)')
    assert dialog.bounding_box()['y'] != second.bounding_box()['y']
    second.locator('[data-tutorial-close]').click(); expect(page.locator('.tutorial-dialog')).to_have_count(1)
    page.set_viewport_size({'width': 1920, 'height': 1080})
    dialog.locator('[data-tutorial-maximize]').click(); expect(dialog.locator('main')).to_be_visible()
    close_all()
    mode['fail'] = 'detail'; page.locator('[data-tutorial]').first.click(); expect(page.locator('.tutorial-dialog [role=alert]')).to_have_text('fixture unavailable')
    mode['fail'] = None; page.locator('.tutorial-dialog main button').click(); opened(); close_all()
    mode['hold'] = 'detail'; page.locator('[data-tutorial]').first.click(); page.wait_for_timeout(100); assert held
    close_all(); mode['hold'] = None; held.pop().fulfill(status=503, json={'detail': 'closed detail'}); page.wait_for_timeout(50)
    assert 'closed detail' not in page.locator('body').inner_text()
    # List failures and changed All batches preserve the last valid result.
    mode['drift'] = True; page.locator('#tutorialRefresh').click(); expect(error).to_contain_text('数据已变化'); assert table.locator('tbody tr').count() == 225
    mode['drift'] = False; mode['fail'] = 'list'; page.locator('#tutorialRefresh').click(); expect(error).to_have_text('fixture unavailable')
    mode['fail'] = None; page.locator('#tutorialRefresh').click(); ready(225)
    mode['hold'] = 'list'; page.locator('#tutorialRefresh').click(); page.wait_for_timeout(100); assert held
    mode['hold'] = None; page.locator('#tutorialRefresh').click(); ready(225)
    held.pop().fulfill(status=503, json={'detail': 'stale list'}); page.wait_for_timeout(50); ready(225)
    page.locator('[data-action=cards]').click(); assert table.locator('article').count() == 225
    assert not table.locator('strong').first.inner_text().endswith(':')
    page.evaluate("location.hash='members'"); table.wait_for(state='detached'); page.evaluate("location.hash='book'")
    table.locator('article').first.wait_for(); page.locator('[data-action=cards]').click(); ready(225)
    assert table.locator('th[data-field=updated_at]').count() == 1
    # Responsive list and windows stay within the viewport after animation settles.
    for width in [1920, 1024, 390]:
        page.set_viewport_size({'width': width, 'height': 844})
        page.evaluate('async()=>{await Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{})))}')
        assert page.locator('#content').evaluate('n=>n.scrollWidth<=n.clientWidth+1'), width
        page.locator('[data-tutorial]').first.click(); dialog, frame = opened()
        assert dialog.evaluate('n=>{const r=n.getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight}')
        frame.locator('img').first.evaluate('async n=>{await n.decode();if(n.naturalWidth===0)throw Error("blank image")}')
        page.screenshot(path='visual-baseline/verified/book-detail-'+str(width)+'.png')
        close_all()
    page.locator('[data-action=cards]').click(); assert page.locator('#content').evaluate('n=>n.scrollWidth<=n.clientWidth+1')
    page.set_viewport_size({'width': 1920, 'height': 1080})
    mode['hold'] = 'list'; page.locator('#tutorialRefresh').click(); page.wait_for_timeout(100); assert held
    page.evaluate("location.hash='members'"); table.wait_for(state='detached'); held.pop().fulfill(status=503, json={'detail': 'closed list'})
    page.wait_for_timeout(50); assert 'closed list' not in page.locator('body').inner_text()
    assert not errors, errors; browser.close()
print('Tutorials: selection, both dates/sorts, columns/cards, paging/All, 12 exports, isolated rich text/images, multiple windows/drag/min/max, failures/stale responses and responsive checks passed')
