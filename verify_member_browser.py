import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path('visual-baseline/verified')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/#members')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    with page.expect_response(lambda r: '/members?' in r.url) as response:
        page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    assert response.value.ok, response.value.status
    page.locator('.member-filters').wait_for()
    assert page.locator('.member-filters label').count() == 10
    page.locator('tbody tr').first.wait_for()
    page.screenshot(path=str(out/'members.png'), full_page=True)
    page.locator('[data-mf=username]').fill('no-such-member-ui-check')
    with page.expect_response(lambda r: '/members?' in r.url) as response:
        page.locator('#memberFilterSubmit').click()
    print('Filter response total:', response.value.json().get('total'), flush=True)
    assert response.value.json().get('total') == 0, 'Running backend ignores username filter'
    page.wait_for_function("document.querySelector('[data-mf=username]')?.value==='no-such-member-ui-check' && document.querySelector('.empty')")
    assert 'username=no-such-member-ui-check' in response.value.url
    with page.expect_response(lambda r: '/members?' in r.url):
        page.locator('#memberFilterReset').click()
    page.locator('tbody tr').first.wait_for()
    assert page.locator('[data-mf=username]').input_value() == ''
    assert page.locator('.vip-badge').count() > 0
    assert page.locator('[role=switch]').count() > 0
    page.screenshot(path=str(out/'members.png'), full_page=True)
    assert not errors, errors
    (out/'members.json').write_text(json.dumps({'route':'#members','viewport':[1920,1080],'screenshot':'members.png','checks':['login','filter request','filter persistence','reset','VIP badge','switch rendering','no browser exceptions'],'backend':'existing service; recovered source deployment not verified'},ensure_ascii=False,indent=2), encoding='utf-8')
    print('Member browser checks passed; screenshot: visual-baseline/verified/members.png')
    browser.close()
