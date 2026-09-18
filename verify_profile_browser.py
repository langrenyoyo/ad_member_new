from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1920,'height':1080})
    errors=[]
    page.on('pageerror', lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/#profile')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('#profileLogs tbody tr').first.wait_for()
    name=page.locator('#profileForm [name=display_name]').input_value()
    page.locator('#profileForm [name=display_name]').fill('Unsaved edit')
    page.locator('#profileForm [type=reset]').click()
    assert page.locator('#profileForm [name=display_name]').input_value()==name
    with page.expect_response(lambda r:'/api/auth/me' in r.url and r.request.method=='PATCH') as response:
        page.locator('#profileForm [type=submit]').click()
    assert response.value.ok
    page.wait_for_function("document.querySelector('#profileMessage')?.textContent.includes('保存成功')")
    page.locator('#profileLogSearch').fill('no-such-operation-record')
    page.wait_for_function("document.querySelector('#profileLogs')?.textContent.includes('暂无数据')")
    page.locator('#profileLogSearch').fill('')
    page.wait_for_function("document.querySelector('#profileLogs input[readonly]')")
    page.reload(wait_until='networkidle')
    page.locator('#profileLogs input[readonly]').first.wait_for()
    Path('visual-baseline/verified').mkdir(exist_ok=True,parents=True)
    page.screenshot(path='visual-baseline/verified/profile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('Profile browser: form reset, save, log search and rendering passed')
