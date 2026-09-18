from uuid import uuid4
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/#risk-whitelist')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('#whitelistTable table').wait_for()
    assert not page.locator('#whitelistFilters').is_visible()
    page.screenshot(path='visual-baseline/verified/risk-whitelist.png',full_page=True)
    token=page.evaluate('state.token');headers={'Authorization':'Bearer '+token}
    username='white-test-'+uuid4().hex[:10]
    response=page.request.post('http://127.0.0.1:3010/api/v1/members',headers=headers,data={'username':username,'name':'Temporary whitelist test','is_white':1})
    assert response.status==201,response.status
    member_id=response.json()['id']
    try:
        page.locator('#whitelistSearch').click()
        page.fill('#whitelistFilters [name=username]',username)
        page.locator('#whitelistFilters [type=submit]').click()
        button=page.locator(f'[data-whitelist-id="{member_id}"][data-field=is_white]')
        button.wait_for()
        assert button.get_attribute('aria-checked')=='true'
        with page.expect_response(lambda response:response.request.method=='PATCH' and f'/members/{member_id}' in response.url) as update:
            button.click()
        assert update.value.ok
        page.locator('#whitelistTable .ads-empty').wait_for()
        assert page.locator('#whitelistFilters [name=username]').input_value()==username
        page.locator('#whitelistFilters [type=reset]').click()
        page.wait_for_function("document.querySelector('#whitelistFilters [name=username]')?.value===''")
        assert not errors,errors
    finally:
        cleanup=page.request.delete(f'http://127.0.0.1:3010/api/v1/members/{member_id}',headers=headers)
        assert cleanup.status==204,cleanup.status
        browser.close()
    print('Whitelist browser checks passed: collapsed filters, query, removal, reset, fixture cleanup')
