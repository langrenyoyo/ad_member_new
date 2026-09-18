"""Exercise rejected filters, retry and out-of-order list responses without writes."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();errors=[];held=[];fail_initial=True
    page.on('pageerror',lambda error:errors.append(str(error)))
    def payload(name):return {'total':1,'items':[{'id':9000,'username':name,'game_id':1,'status':1}]}
    def respond(route):
        global fail_initial
        query=parse_qs(urlparse(route.request.url).query)
        if fail_initial:
            fail_initial=False;route.fulfill(status=503,json={'detail':'暂时不可用'});return
        if query.get('create_time')==['invalid']:
            route.fulfill(status=422,json={'detail':'创建时间格式无效'});return
        name=query.get('username',['initial-row'])[0]
        if name=='slow-old':
            held.append(route);page.evaluate('window.memberSlowPending=true');return
        route.fulfill(json=payload(name))
    page.route('**/api/v1/members?*',respond)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.get_by_text('暂时不可用',exact=True).wait_for()
    page.locator('#pageLoadError button').click();page.locator('.member-filters').wait_for()
    page.fill('[data-mf=create_time]','invalid');page.locator('#memberFilterSubmit').click()
    page.get_by_text('创建时间格式无效',exact=True).wait_for()
    assert page.locator('[data-mf=create_time]').input_value()=='invalid'
    page.locator('#memberFilterReset').click();page.locator('#pageLoadError').wait_for(state='detached')
    page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    page.fill('[data-mf=username]','slow-old');page.locator('#memberFilterSubmit').click()
    page.wait_for_function('window.memberSlowPending===true')
    assert held
    page.fill('[data-mf=username]','new-result');page.locator('#memberFilterSubmit').click()
    page.get_by_text('new-result',exact=False).last.wait_for()
    held[0].fulfill(json=payload('slow-old'))
    page.wait_for_load_state('networkidle')
    assert 'new-result' in page.locator('tbody').inner_text() and 'slow-old' not in page.locator('tbody').inner_text()
    assert page.locator('[data-mf=username]').input_value()=='new-result'
    assert not errors,errors
    browser.close()
print('Members: initial retry, invalid filter recovery, retained input and latest response wins passed')
