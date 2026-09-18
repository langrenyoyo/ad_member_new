"""Exercise subsidy CRUD with synthetic API data, never business writes."""
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent
row = dict(id=7, user_id=12, status=0, tx_price=10, price=2.5,
           receive_name='Fixture recipient', receive_tel='00123', pics='', sub_msg='')
permissions = dict(edit=True, delete=True, review=True)
writes, reads, errors = [], [], []
failure = False

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport=dict(width=1440, height=1000))
    page.on('pageerror', lambda error: errors.append(str(error)))

    def fixture(route):
        request = route.request
        path = urlparse(request.url).path
        if path.startswith('/api/auth/'):
            path = 'auth/' + path.removeprefix('/api/auth/')
        else:
            path = path.removeprefix('/api/v1/')
        if path == 'auth/login':
            route.fulfill(json=dict(access_token='fixture', user=dict(username='fixture')))
        elif request.method != 'GET':
            writes.append(dict(path=path, method=request.method, body=request.post_data_json))
            route.fulfill(status=503 if failure else 200,
                          json=dict(detail='Fixture failure') if failure else row)
        else:
            reads.append(path)
            if path == 'subsidies/7':
                route.fulfill(json=row)
            elif path == 'subsidies':
                route.fulfill(json=dict(items=[row, {**row, 'id': 8}], total=2, permissions=permissions))
            else:
                route.fulfill(json=dict(items=[], total=0))

    page.route('**/api/**', fixture)
    page.goto('http://127.0.0.1:3000/#subsidies')
    page.fill('#loginForm [name=username]', 'fixture')
    page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-subsidy-edit="7"]').wait_for()
    expect(page.locator('#subsidyEdit')).to_be_disabled()
    expect(page.locator('#subsidyDelete')).to_be_disabled()

    def open_editor():
        page.locator('[data-subsidy-edit="7"]').click()
        expect(page.locator('.subsidy-form-fields')).to_be_visible()

    def submit():
        page.locator('#editorForm').evaluate('f=>f.requestSubmit()')

    open_editor()
    assert 'subsidies/7' in reads
    expect(page.locator('#editorForm [name=receive_tel]')).to_have_value('00123')
    page.locator('#editorForm [name=price]').fill('3.75')
    submit()
    expect(page.locator('#modal')).to_be_hidden()
    assert writes[-1] == dict(path='subsidies/7', method='PATCH', body=dict(price=3.75))
    open_editor()
    submit()
    expect(page.locator('#modal')).to_be_hidden()
    assert len(writes) == 1
    open_editor()
    page.locator('#editorForm [name=price]').fill('')
    submit()
    expect(page.locator('.subsidy-form-error')).not_to_be_empty()
    assert len(writes) == 1
    page.locator('#editorForm [name=price]').fill('2.5')
    page.locator('#editorForm [name=status]').select_option('4')
    submit()
    expect(page.locator('.subsidy-form-error')).not_to_be_empty()
    assert len(writes) == 1
    failure = True
    page.locator('#editorForm [name=sub_msg]').fill('Fixture reason')
    submit()
    expect(page.locator('.subsidy-form-error')).to_have_text('Fixture failure')
    expect(page.locator('#editorForm [name=sub_msg]')).to_have_value('Fixture reason')
    expect(page.locator('#editorForm [type=submit]')).to_be_enabled()
    assert writes[-1]['body'] == dict(status=4, sub_msg='Fixture reason')
    failure = False
    submit()
    expect(page.locator('#modal')).to_be_hidden()

    page.locator('[data-subsidy-delete="7"]').click()
    page.locator('.withdrawal-confirm footer [value=cancel]').click()
    assert len(writes) == 3
    failure = True
    page.locator('[data-subsidy-delete="7"]').click()
    page.locator('.withdrawal-confirm-ok').click()
    expect(page.locator('#reviewError')).to_have_text('Fixture failure')
    expect(page.locator('[data-subsidy-delete="7"]')).to_be_enabled()
    assert writes[-1] == dict(path='subsidies/7', method='DELETE', body=None)
    failure = False
    page.locator('#subsidySelectAll').check()
    expect(page.locator('#subsidyEdit')).to_be_disabled()
    expect(page.locator('#subsidyDelete')).to_be_enabled()
    page.locator('#subsidyDelete').click()
    page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_timeout(200)
    assert len(writes) == 5, writes
    expect(page.locator('#subsidyDelete')).to_be_disabled()
    assert writes[-1] == dict(path='subsidies/batch-delete', method='POST', body=dict(ids=[7, 8]))

    # Deferred writes cannot submit twice or repaint a newer route.
    open_editor()
    page.evaluate("""() => {
      window.savedApi=api;window.deferredWrites=0;
      window.api=(url, options)=>options?.method==='PATCH'
        ?(deferredWrites++,new Promise(resolve=>window.finishWrite=resolve)):savedApi(url,options);
    }""")
    page.locator('#editorForm [name=price]').fill('9')
    submit()
    submit()
    assert page.evaluate('deferredWrites') == 1
    expect(page.locator('#editorForm [type=submit]')).to_be_disabled()
    page.evaluate("location.hash='withdrawals'")
    expect(page.locator('#modal')).to_be_hidden()
    page.wait_for_function("state.view==='withdrawals'")
    page.evaluate('finishWrite({});api=savedApi')
    page.wait_for_timeout(100)
    assert page.evaluate('state.view') == 'withdrawals'
    page.evaluate("location.hash='subsidies'")
    page.locator('[data-subsidy-edit="7"]').wait_for()
    page.screenshot(path=str(ROOT/'visual-baseline/verified/subsidy-crud-desktop.png'), full_page=True)
    open_editor()
    page.screenshot(path=str(ROOT/'visual-baseline/verified/subsidy-editor-desktop.png'))
    page.set_viewport_size(dict(width=390, height=844))
    assert page.locator('.subsidy-form-fields').evaluate('e=>e.scrollWidth<=e.clientWidth')
    page.screenshot(path=str(ROOT/'visual-baseline/verified/subsidy-editor-mobile.png'))
    page.locator('[data-subsidy-form-cancel]').click()
    permissions.update(edit=False, delete=False, review=False)
    page.evaluate("renderReviewPage('subsidies')")
    assert page.locator('[data-subsidy-edit],[data-subsidy-delete]').count() == 0
    for selector in ['#subsidyEdit', '#subsidyDelete', '[data-subsidy-batch="approve"]', '[data-subsidy-batch="reject"]']:
        expect(page.locator(selector)).to_be_hidden()
    assert not errors, errors
    browser.close()
print('PASS: subsidy edit/delete, validation, permissions, retry, batch deletion, duplicate submission and route isolation (fixture).')
