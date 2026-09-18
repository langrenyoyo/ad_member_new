"""Exercise profile form, avatars, logs and lifecycle with intercepted synthetic data."""
import csv
import io
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image
from playwright.sync_api import sync_playwright, expect

AVATAR = '/api/member-images/'+'a'*48+'.png'
bitmap = io.BytesIO(); Image.new('RGB', (24, 24), (40, 160, 100)).save(bitmap, format='PNG')
user = {'id': 8000, 'username': 'fixture', 'display_name': 'Fixture Administrator', 'mobile': '13800000000', 'avatar': '/assets/img/avatar.png'}
rows = [{'id': 9100+i, 'title': 'fixture <>& '+str(i), 'path': '/fixture/'+str(i), 'ip': '192.0.2.'+str(i % 250+1),
    'created_at': (datetime(2026, 9, 18, tzinfo=timezone.utc)+timedelta(minutes=i % 3)).isoformat()} for i in range(225)]
reads = []; writes = []; held = []; errors = []; me_reads = []
mode = {'hold': None, 'fail': None, 'drift': False}
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda error: errors.append(str(error)))

    def fixture(route):
        request = route.request; url = urlparse(request.url); path = url.path.removeprefix('/api/'); q = parse_qs(url.query)
        if path == 'auth/login': route.fulfill(json={'access_token': 'fixture', 'user': user}); return
        if url.path == AVATAR: route.fulfill(content_type='image/png', body=bitmap.getvalue()); return
        kind = {'auth/avatar': 'upload', 'auth/operations': 'logs', 'auth/me': 'save' if request.method == 'PATCH' else 'me'}.get(path)
        if kind in ['upload', 'save']: writes.append((kind, request.post_data_json if kind == 'save' else len(request.post_data_buffer)))
        else: assert request.method == 'GET', request.url
        if kind == 'logs': reads.append(q)
        if kind == 'me':
            me_reads.append(request.url)
            if mode.get('hold_me_at') == len(me_reads): held.append((kind, route)); return
        if kind and mode['hold'] == kind: held.append((kind, route)); return
        if kind and mode['fail'] == kind: route.fulfill(status=403, json={'detail': 'fixture denied'}); return
        if kind == 'me': route.fulfill(json=user); return
        if kind == 'upload': route.fulfill(status=201, json={'url': AVATAR}); return
        if kind == 'save':
            user.update({key: value for key, value in request.post_data_json.items() if key != 'password'})
            route.fulfill(json=user); return
        if kind == 'logs':
            items = [row for row in rows if q.get('q', [''])[0] in ' '.join([row['title'], row['path'], row['ip']])]
            items.sort(key=lambda r: r['id'], reverse=True)
            items.sort(key=lambda r: r[q.get('sort', ['id'])[0]], reverse=q.get('order', ['desc'])[0] == 'desc')
            offset = int(q.get('offset', ['0'])[0]); limit = int(q.get('limit', ['10'])[0])
            route.fulfill(json={'items': items[offset:offset+limit], 'total': len(items)+(1 if mode['drift'] and offset else 0)}); return
        route.fulfill(json={'items': [], 'total': 0})

    page.route('**/api/**', fixture)
    page.goto('http://127.0.0.1:3000/#profile')
    page.fill('#loginForm [name=username]', 'fixture'); page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    form = page.locator('#profileForm'); table = page.locator('#profileLogTable'); error = page.locator('#profileLogError')
    name = form.locator('[name=display_name]'); password = form.locator('[name=password]'); message = page.locator('#profileMessage')

    def ready(count=10):
        page.wait_for_function('n=>document.querySelector("#profileLogTable tbody")?.rows.length===n&&!document.querySelector("#profileLogTable").hasAttribute("aria-busy")', arg=count)
        assert error.inner_text() == '', error.inner_text()

    def search(value, count=10):
        page.locator('#profileLogSearch').fill(value); page.locator('#profileLogSearch').press('Enter'); ready(count)

    def submit(): form.evaluate('f=>f.requestSubmit()')

    def upload(): page.locator('#profileAvatarFile').set_input_files({'name': 'fixture.png', 'mimeType': 'image/png', 'buffer': bitmap.getvalue()})

    def reset(): form.locator('[type=reset]').click()

    def release(body=None, status=200):
        kind, route = held.pop(0)
        route.fulfill(status=status, json=body if body is not None else user)

    def leave():
        page.evaluate("location.hash='members'"); table.wait_for(state='detached')

    def back():
        page.evaluate("location.hash='profile'"); form.wait_for()

    ready()
    assert reads[-1] == {'limit': ['10'], 'offset': ['0'], 'sort': ['id'], 'order': ['desc']}
    assert form.locator('input:disabled').count() == 2
    assert not page.locator('#profileAvatarFile').is_visible()
    assert table.locator('[data-sort]').count() == 1
    assert table.locator('.profile-log-link input').first.is_editable()
    assert table.locator('.profile-log-link a').first.get_attribute('href').endswith('/fixture/224')
    count = len(reads); table.locator('.game-user-cell-search').first.click(); assert len(reads) == count
    name.fill('Unsaved'); password.fill('Not-Saved-123!'); reset()
    expect(name).to_have_value(user['display_name']); expect(password).to_have_value('')
    # Validation, preview, reset, upload cancellation and failure recovery.
    count = len(writes)
    page.locator('#profileAvatarFile').set_input_files({'name': 'bad.svg', 'mimeType': 'image/svg+xml', 'buffer': b'<svg/>'})
    expect(message).to_contain_text('PNG'); assert len(writes) == count
    page.locator('#profileAvatarFile').set_input_files({'name': 'large.png', 'mimeType': 'image/png', 'buffer': b'x'*(2*1024*1024+1)})
    expect(message).to_contain_text('2MB'); assert len(writes) == count
    mode['fail'] = 'upload'; upload(); expect(message).to_have_text('fixture denied')
    mode['fail'] = None; upload(); expect(message).to_have_text('上传成功')
    assert user['avatar'] == '/assets/img/avatar.png'
    expect(page.locator('.profile-avatar')).to_have_attribute('src', AVATAR)
    assert page.locator('.profile-avatar').evaluate('async n=>{await n.decode();const c=document.createElement("canvas");c.width=c.height=1;const x=c.getContext("2d");x.drawImage(n,0,0,1,1);return [...x.getImageData(0,0,1,1).data].join(",")}') == '40,160,100,255'
    reset(); expect(page.locator('.profile-avatar')).to_have_attribute('src', user['avatar'])
    mode['hold'] = 'upload'; upload(); page.wait_for_timeout(50); assert held
    expect(form.locator('[type=submit]')).to_be_disabled(); reset(); mode['hold'] = None
    release({'url': AVATAR}, 201); page.wait_for_timeout(50)
    expect(page.locator('.profile-avatar')).to_have_attribute('src', user['avatar'])
    # Failed and duplicate saves retain form data; successful saves update reset defaults and shell.
    upload(); expect(message).to_have_text('上传成功'); name.fill('Saved <>&'); password.fill('Changed-12345!')
    mode['fail'] = 'save'; submit(); expect(message).to_have_text('fixture denied'); expect(name).to_have_value('Saved <>&')
    mode['fail'] = None; mode['hold'] = 'save'; before = len(writes); submit()
    page.wait_for_timeout(50); assert held and len(writes) == before+1
    submit(); page.wait_for_timeout(50); assert len(writes) == before+1
    assert writes[-1][1] == {'display_name': 'Saved <>&', 'password': 'Changed-12345!', 'avatar': AVATAR}
    expect(form.locator('[type=reset]')).to_be_disabled()
    mode['hold'] = None; user.update({'display_name': 'Saved <>&', 'avatar': AVATAR}); release()
    expect(message).to_have_text('保存成功'); expect(form).not_to_have_attribute('aria-busy', 'true')
    expect(password).to_have_value(''); expect(page.locator('#profileName')).to_have_text(user['display_name'])
    expect(page.locator('.target-user-label')).to_have_text(user['display_name'])
    expect(page.locator('.target-avatar')).to_have_attribute('src', AVATAR)
    assert AVATAR in page.locator('.target-user-label').evaluate('n=>getComputedStyle(n,"::before").backgroundImage')
    name.fill('Reset again'); reset(); expect(name).to_have_value(user['display_name'])
    submit(); expect(message).to_have_text('保存成功'); expect(form).not_to_have_attribute('aria-busy', 'true')
    assert 'password' not in writes[-1][1]
    page.reload(); ready(); expect(page.locator('.profile-avatar')).to_have_attribute('src', AVATAR)
    expect(page.locator('.target-avatar')).to_have_attribute('src', AVATAR)
    leave(); page.reload(); page.locator('.member-filters').wait_for()
    expect(page.locator('#accountName')).to_have_text(user['display_name'])
    expect(page.locator('.target-avatar')).to_have_attribute('src', AVATAR)
    toggle = page.locator('.shell-sidebar-toggle'); toggle.click()
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    toggle.click(); expect(toggle).to_have_attribute('aria-expanded', 'true')
    back(); ready()
    mode['hold_me_at'] = len(me_reads)+2; stale_user = dict(user)
    page.reload(); ready(); assert held and held[0][0] == 'me'
    name.fill('Newer identity'); submit(); expect(message).to_have_text('保存成功')
    expect(form).not_to_have_attribute('aria-busy', 'true'); release(stale_user)
    page.wait_for_timeout(50); expect(page.locator('.target-user-label')).to_have_text('Newer identity')
    # Search debounce, Enter cancellation, date sort, cyclic pagination, jump and All.
    count = len(reads); page.locator('#profileLogSearch').fill('fixture <>& 224')
    page.wait_for_timeout(150); assert len(reads) == count
    ready(1); assert reads[-1]['q'] == ['fixture <>& 224']
    search(''); page.wait_for_timeout(550); count = len(reads)
    page.locator('#profileLogSearch').fill('fixture <>& 224'); page.locator('#profileLogSearch').press('Enter'); ready(1)
    page.wait_for_timeout(550); assert len(reads) == count+1
    search('')
    page.locator('#profileLogPagination [aria-label="上一页"]').click(); ready(5); assert reads[-1]['offset'] == ['220']
    page.locator('#profileLogPagination [aria-label="下一页"]').click(); ready()
    page.locator('#profileLogPagination input').fill('5'); page.locator('[data-game-jump]').click(); ready(); assert reads[-1]['offset'] == ['40']
    for order in ['desc', 'asc']:
        table.locator('[data-sort=created_at]').click(); ready(); assert reads[-1]['order'] == [order] and reads[-1]['offset'] == ['0']
    page.locator('#profileLogPagination .game-page-size summary').click(); page.locator('[data-game-size=All]').click(); ready(225)
    assert reads[-2]['limit'] == ['200'] and reads[-1]['offset'] == ['200']
    for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download: page.locator('[data-export='+kind+']').click()
        content = Path(download.value.path()).read_bytes()
        assert b'fixture' in content and b'<input' not in content
        if kind == 'json':
            result = json.loads(content); assert len(result['data']) == 225 and result['header'][0] == ['标题', '链接', 'ip', '操作时间']
            assert all(row['链接'] == 0 for row in result['data'])
        if kind == 'xml': assert 'fixture <>& 224' in ''.join(ET.fromstring(content).itertext())
        if kind == 'csv': assert len(list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))) == 226
    page.locator('.game-user-columns summary').click(); page.locator('[data-column=id]').uncheck(); page.locator('[data-column=ip]').uncheck(); page.locator('.game-user-columns summary').click()
    page.locator('.game-user-export summary').click()
    with page.expect_download() as download: page.locator('[data-export=json]').click()
    assert json.loads(Path(download.value.path()).read_bytes())['header'][0] == ['链接', '操作时间']
    page.locator('[data-action=cards]').click(); assert table.locator('article').count() == 225
    assert not table.locator('strong').first.inner_text().endswith(':')
    leave(); back(); table.locator('article').first.wait_for(); page.locator('[data-action=cards]').click(); ready(225)
    assert table.locator('th').count() == 3
    search('not-found', 1); expect(table).to_contain_text('没有找到匹配的记录'); assert not page.locator('#profileLogPagination').is_visible()
    search('fixture <>& 224', 1); name.fill('Filtered save'); submit(); expect(message).to_have_text('保存成功'); expect(form).not_to_have_attribute('aria-busy', 'true')
    assert reads[-1]['q'] == ['fixture <>& 224']; search('', 225)
    # A changing All response and failed refresh retain the previous valid table.
    mode['drift'] = True; page.locator('#profileLogRefresh').click(); expect(error).to_contain_text('数据已变化'); assert table.locator('tbody tr').count() == 225
    mode['drift'] = False; mode['fail'] = 'logs'; page.locator('#profileLogRefresh').click(); expect(error).to_have_text('fixture denied')
    mode['fail'] = None; page.locator('#profileLogRefresh').click(); ready(225)
    mode['hold'] = 'logs'; page.locator('#profileLogRefresh').click(); page.wait_for_timeout(50); assert held
    mode['hold'] = None; search('fixture <>& 224', 1); release({'detail': 'stale logs'}, 503); page.wait_for_timeout(50); ready(1)
    # Mobile constraints and actual avatar pixels, including cards.
    for width in [1920, 1024, 390]:
        page.set_viewport_size({'width': width, 'height': 844})
        page.evaluate('async()=>{await Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{})))}')
        assert page.locator('#content').evaluate('n=>n.scrollWidth<=n.clientWidth+1'), width
        if width == 390: assert page.locator('.sidebar').evaluate('n=>n.getBoundingClientRect().right<=0')
        assert page.locator('.profile-avatar').evaluate('n=>n.complete&&n.naturalWidth===24')
        page.screenshot(path='visual-baseline/verified/profile-'+str(width)+'.png', full_page=True)
    page.locator('[data-action=cards]').click()
    assert page.locator('#content').evaluate('n=>n.scrollWidth<=n.clientWidth+1')
    page.locator('[data-action=cards]').click()
    # Late read/upload/save responses cannot overwrite the next page or next profile session.
    page.set_viewport_size({'width': 1920, 'height': 1080})
    mode['hold'] = 'upload'; upload(); page.wait_for_timeout(50); assert held
    leave(); mode['hold'] = None; back(); ready(1); release({'detail': 'closed upload'}, 403)
    page.wait_for_timeout(50); expect(message).to_have_text('')
    mode['hold'] = 'save'; name.fill('Closed save'); submit(); page.wait_for_timeout(50); assert held
    leave(); mode['hold'] = None; back(); ready(1)
    release({**user, 'display_name': 'Closed save'}); page.wait_for_timeout(50)
    expect(name).to_have_value(user['display_name']); expect(page.locator('.target-user-label')).to_have_text(user['display_name'])
    leave(); mode['fail'] = 'me'; back_error = page.locator('.profile-loading [role=alert]')
    page.evaluate("location.hash='profile'"); expect(back_error).to_have_text('fixture denied')
    mode['fail'] = None; page.locator('.profile-loading button').click(); ready(1)
    leave(); mode['hold'] = 'me'; page.evaluate("location.hash='profile'"); page.wait_for_timeout(100); assert held
    page.evaluate("location.hash='members'"); page.locator('.profile-loading').wait_for(state='detached')
    mode['hold'] = None; release({**user, 'display_name': 'Stale profile'})
    page.wait_for_timeout(50); assert not form.count() and 'Stale profile' not in page.locator('.target-user-label').inner_text()
    assert not errors, errors
    browser.close()
print('Profile: form/reset/password, avatar validation/preview/save/reload, duplicate lock, private log table controls, six exports, responsive pixels and stale-response isolation passed')
