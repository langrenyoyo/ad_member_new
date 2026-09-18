"""Exercise pending withdrawal edit with isolated responses; no business writes."""
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent
row = dict(id=41, user_id=12, status=0, plan_status=0, good_name='Fixture product',
           device_manufacturer='Fixture phone', receive_name='Recipient', receive_tel='00123',
           receive_address='Fixture address', exchange_value=125, exchange_type=1,
           delivery_name='', delivery_no='', remark='Original note', sub_msg='')
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
            key = 'auth/' + path.removeprefix('/api/auth/')
        else:
            key = path.removeprefix('/api/v1/')
        if key == 'auth/login':
            route.fulfill(json=dict(access_token='fixture', user=dict(username='fixture')))
        elif request.method != 'GET':
            writes.append(dict(path=key, method=request.method, body=request.post_data_json))
            route.fulfill(status=503 if failure else 200,
                          json=dict(detail='Fixture failure') if failure else row)
        else:
            reads.append(key)
            if key == 'withdrawals/41':
                route.fulfill(json=row)
            elif key == 'withdrawals':
                route.fulfill(json=dict(items=[row], total=1,
                                        summary=dict(withdrawn=0, pending=125, blacklisted=None),
                                        permissions=dict(edit=True, review=True, transfer=True, blacklist=True)))
            else:
                route.fulfill(json=dict(items=[], total=0))

    page.route('**/api/**', fixture)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]', 'fixture')
    page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-withdrawal-edit="41"]').wait_for()
    expect(page.locator('#withdrawalEdit')).to_be_disabled()
    page.locator('[data-withdrawal-edit="41"]').click()
    expect(page.locator('.withdrawal-form-fields')).to_be_visible()
    assert 'withdrawals/41' in reads
    expect(page.locator('#formFields [name=receive_tel]')).to_have_value('00123')
    page.locator('#formFields [name=good_name]').fill('Updated product')
    page.locator('#editorForm').evaluate('f=>f.requestSubmit()')
    expect(page.locator('#modal')).to_be_hidden()
    assert writes[-1] == dict(path='withdrawals/41', method='PATCH', body={'good_name': 'Updated product'})

    page.locator('[data-withdrawal-edit="41"]').click()
    page.locator('#formFields [name=exchange_value]').fill('-1')
    page.locator('#editorForm').evaluate('f=>f.requestSubmit()')
    expect(page.locator('.subsidy-form-error')).not_to_be_empty()
    assert len(writes) == 1
    page.locator('#formFields [name=exchange_value]').fill('130')
    failure = True
    page.locator('#formFields [name=remark]').fill('Retry note')
    page.locator('#editorForm').evaluate('f=>f.requestSubmit()')
    expect(page.locator('.subsidy-form-error')).to_have_text('Fixture failure')
    expect(page.locator('#formFields [name=remark]')).to_have_value('Retry note')
    expect(page.locator('#editorForm [type=submit]')).to_be_enabled()
    assert writes[-1]['body'] == {'exchange_value': 130, 'remark': 'Retry note'}

    page.evaluate("location.hash='members'")
    page.wait_for_function("state.view==='members'")
    page.evaluate("location.hash='withdrawals'")
    page.locator('[data-withdrawal-edit="41"]').wait_for()
    page.screenshot(path=str(ROOT / 'visual-baseline' / 'verified' / 'withdrawal-edit-desktop.png'), full_page=True)
    page.locator('[data-withdrawal-edit="41"]').click()
    page.set_viewport_size(dict(width=390, height=844))
    assert page.locator('.withdrawal-form-fields').evaluate('e=>e.scrollWidth<=e.clientWidth')
    page.screenshot(path=str(ROOT / 'visual-baseline' / 'verified' / 'withdrawal-edit-mobile.png'))
    assert not errors, errors
    browser.close()
print('PASS: pending withdrawal edit, detail loading, field diff, validation, failure retention and route isolation (fixture).')
