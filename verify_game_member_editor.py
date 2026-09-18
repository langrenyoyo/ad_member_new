"""Nested game editor regression; every write is intercepted in the browser."""
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    row = dict(id=987654, game_id=9300, username='fixture', name='original',
               status=1, coin=12, game_addiction_time='2026-09-17 12:34:56')
    errors, reads, writes, lists = [], [], [], []
    mode = {'delay': False}
    page.on('pageerror', lambda error: errors.append(str(error)))

    def api(route):
        path = route.request.url.split('/api/', 1)[1].split('?', 1)[0]
        if path == 'auth/login':
            route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}})
        elif path == 'v1/members/987654':
            if route.request.method == 'PATCH':
                writes.append(route)
            elif mode['delay']:
                reads.append(route)
            else:
                route.fulfill(json=row)
        elif path == 'v1/member-images':
            route.fulfill(status=201, json={'url': '/api/member-images/fixture.png'})
        elif path == 'member-images/fixture.png':
            route.fulfill(content_type='image/png', body=avatar.getvalue())
        else:
            assert route.request.method == 'GET', route.request.url
            if path == 'v1/members':
                lists.append(route.request.url)
                route.fulfill(json={'total': 1, 'items': [row]})
            elif path == 'v1/games':
                route.fulfill(json={'total': 1, 'items': [{'id': 9300, 'name': 'fixture game', 'status': 1}]})
            else:
                route.fulfill(json={'total': 0, 'items': []})

    avatar = BytesIO()
    Image.new('RGB', (4, 4), 'green').save(avatar, format='PNG')
    page.route('**/api/**', api)
    page.goto('http://127.0.0.1:3000/#games')
    page.fill('#loginForm [name=username]', 'fixture')
    page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    pane = page.locator('#game-user-pane-four')
    host = page.locator('.game-member-editor-host')
    modal = page.locator('#modal')
    form = page.locator('#editorForm')

    def settle():
        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')

    def open_parent():
        page.locator('[data-game-user="9300"]').click()
        page.locator('[data-tab=four]').click()
        pane.locator('[data-game-member-edit]').wait_for()

    def open_editor():
        pane.locator('[data-game-member-edit]').click()
        host.wait_for(state='visible')

    def submit():
        with page.expect_request('**/api/v1/members/987654'):
            form.evaluate('f=>{f.requestSubmit();f.requestSubmit();}')
        settle()

    def restored():
        host.wait_for(state='detached')
        assert modal.is_hidden()
        assert modal.evaluate('el=>el.parentElement===document.body')

    open_parent()
    pane.locator('tbody td').nth(1).click()
    assert pane.locator('[data-member-select]').is_checked()
    pane.locator('tbody td').nth(1).dblclick()
    host.wait_for(state='visible')
    page.keyboard.press('Escape')
    restored()
    assert pane.locator('[data-member-select]').is_checked()
    pane.locator('[data-member-select]').uncheck()
    assert not pane.locator('[data-member-select]').is_checked()
    open_editor()
    assert host.evaluate('el=>el.matches(":modal") && el.contains(document.activeElement)')
    assert page.locator('[data-member-tab-button]').all_text_contents() == [
        '\u57fa\u7840\u4fe1\u606f', '\u62bd\u5956\u8bbe\u7f6e',
        '\u4e0b\u8f7d\u8bbe\u7f6e', '\u4ee3\u7406\u8bbe\u7f6e']
    window = page.locator('#modal>.modal')
    assert window.bounding_box() == dict(x=560, y=240, width=800, height=600)
    page.locator('[data-member-tab-button=lottery]').click()
    page.fill('[name=raffle_num]', '37')
    page.locator('[data-member-window=maximize]').click()
    assert window.bounding_box() == dict(x=0, y=0, width=1920, height=1080)
    page.locator('[data-member-window=maximize]').click()
    page.locator('[data-member-window=minimize]').click()
    assert not host.evaluate('el=>el.matches(":modal")')
    assert form.is_hidden()
    pane.locator('[data-action=cards]').click()
    assert pane.locator('.game-user-cards').count() == 1
    page.locator('[data-member-window=maximize]').click()
    assert host.evaluate('el=>el.matches(":modal")')
    assert page.locator('[name=raffle_num]').input_value() == '37'
    form.locator('[type=reset]').click()
    page.locator('[data-member-tab-button=basic]').click()
    form.locator('[type=submit]').click()
    restored()
    assert not writes

    # Shared upload and date picker must operate inside the native top layer.
    open_editor()
    page.locator('[data-member-image-file]').set_input_files({
        'name': 'avatar.png', 'mimeType': 'image/png', 'buffer': avatar.getvalue()})
    page.wait_for_function("document.querySelector('[name=image_url]').value==='/api/member-images/fixture.png'")
    page.wait_for_function("document.querySelector('[data-member-image-preview]').naturalWidth===4")
    date = page.locator('[name=game_addiction_time]')
    date.click()
    widget = page.locator('.bootstrap-datetimepicker-widget')
    widget.locator('.day:not(.old):not(.new)').filter(has_text='18').click()
    assert date.input_value() == '2026-09-18 12:34:56'
    widget.locator('[data-action=close]').click()
    form.locator('[type=reset]').click()
    page.wait_for_function("document.querySelector('[name=image_url]').value===''")
    assert date.input_value() == row['game_addiction_time']
    page.fill('#formFields [name=name]', 'changed')
    submit()
    assert len(writes) == 1
    assert writes[0].request.post_data_json == {'name': 'changed'}
    assert form.locator('[type=submit]').is_disabled()
    writes.pop().fulfill(status=403, json={'detail': 'fixture denied'})
    page.locator('.member-edit-error').get_by_text('fixture denied').wait_for()
    assert page.locator('#formFields [name=name]').input_value() == 'changed'
    submit()
    assert len(writes) == 1
    row['name'] = 'changed'
    writes.pop().fulfill(json=row)
    restored()
    settle()

    open_editor()
    page.keyboard.press('Escape')
    restored()
    assert page.locator('.game-user-dialog').is_visible()
    # Wrong-game responses must never be displayed as editable records.
    mode['delay'] = True
    with page.expect_request('**/api/v1/members/987654'):
        pane.locator('[data-game-member-edit]').click()
    settle()
    reads.pop().fulfill(json={**row, 'game_id': 9301})
    pane.locator('[role=alert]').get_by_text('\u4f1a\u5458\u4e0d\u5c5e\u4e8e\u5f53\u524d\u6e38\u620f').wait_for()
    assert host.count() == 0
    # Closing the parent cancels pending reads and prevents a delayed popup.
    with page.expect_request('**/api/v1/members/987654'):
        pane.locator('[data-game-member-edit]').click()
    settle()
    late_read = reads.pop()
    page.locator('[data-dialog-close]').click()
    page.locator('.game-user-dialog').wait_for(state='detached')
    late_read.fulfill(json=row)
    settle()
    assert host.count() == 0 and modal.is_hidden()
    mode['delay'] = False

    # A pending save cannot refresh a closed parent or change a newer editor.
    open_parent()
    open_editor()
    page.fill('#formFields [name=name]', 'old draft')
    submit()
    old_save = writes.pop()
    page.evaluate("document.querySelector('.game-user-dialog').close()")
    restored()
    page.locator('.game-user-dialog').wait_for(state='detached')
    page.evaluate('location.hash="members"')
    page.locator('[data-edit="987654"]').click()
    modal.wait_for(state='visible')
    page.fill('#formFields [name=name]', 'new draft')
    before = len(lists)
    old_save.fulfill(json=row)
    settle()
    assert len(lists) == before
    assert page.locator('#formFields [name=name]').input_value() == 'new draft'
    assert form.locator('[type=submit]').is_enabled()
    page.locator('#closeModal').click()
    page.evaluate('location.hash="games"')
    open_parent()
    open_editor()
    page.evaluate('location.hash="members"')
    restored()
    page.locator('.game-user-dialog').wait_for(state='detached')

    page.evaluate('location.hash="games"')
    open_parent()
    open_editor()
    out = Path('visual-baseline/verified')
    out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out / 'game-member-editor.png'))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert window.evaluate('el=>el.scrollWidth<=el.clientWidth+1 && el.getBoundingClientRect().width<=innerWidth')
    assert form.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    assert page.locator('[data-member-tab-button]').evaluate_all(
        'els=>els.every(el=>el.scrollHeight<=el.clientHeight && el.scrollWidth<=el.clientWidth)')
    page.screenshot(path=str(out / 'game-member-editor-mobile.png'))
    page.locator('#closeModal').click()
    restored()
    page.locator('[data-dialog-close]').click()
    assert not errors, errors
    assert not writes and not reads
    browser.close()

print('Game member editor: scope, tabs, windows, upload/date/reset, no-op and changed-only save, retry, stale responses, parent/navigation cleanup and mobile layout passed')
