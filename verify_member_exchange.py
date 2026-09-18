"""Mocked exchange switch: persisted response, failure, duplicate and stale request."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();reads=[];writes=[];held=[];errors=[]
    value=0;mode='ok'
    def members(route):
        reads.append(route.request.url)
        route.fulfill(json={'total':1,'items':[{'id':9200,'username':'兑换测试','exchange_enable':value,'status':1}]})
    def patch(route):
        global value
        writes.append(route.request.post_data_json)
        if mode=='hold':held.append(route);return
        if mode=='fail':route.fulfill(status=403,json={'detail':'没有兑换修改权限'});return
        value=route.request.post_data_json['exchange_enable'];route.fulfill(json={'id':9200,'exchange_enable':value})
    page.route('**/api/v1/members?*',members);page.route('**/api/v1/members/9200',patch)
    page.on('dialog',lambda dialog:(errors.append(dialog.message),dialog.accept()))
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-columns summary').click();page.locator('[data-member-column=exchange_enable]').check()
    page.locator('.member-columns summary').focus();page.keyboard.press('Escape')
    switch=page.get_by_role('switch',name='兑换',exact=True)
    assert switch.get_attribute('aria-checked')=='false'
    switch.click();page.wait_for_function("document.querySelector('[data-member-exchange]').getAttribute('aria-checked')==='true'")
    assert writes==[{'exchange_enable':1}]
    assert 'agent_id=9000' in reads[-1]
    mode='fail';switch.click();page.wait_for_function("!document.querySelector('[data-member-exchange]').disabled")
    assert errors==['没有兑换修改权限'] and switch.get_attribute('aria-checked')=='true'
    mode='hold';switch.click()
    page.wait_for_function("document.querySelector('[data-member-exchange]').disabled")
    switch.evaluate('e=>e.click()');assert len(writes)==3
    previous=len(reads)
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    held[0].fulfill(json={'id':9200,'exchange_enable':0})
    page.wait_for_load_state('networkidle')
    assert page.locator('.agent-panel').is_visible() and len(reads)==previous
    browser.close()
print('Member exchange: scoped reload, success, denied write, no duplicate request and stale completion passed')
