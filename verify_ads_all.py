"""All rows must not mix delayed batches from different filters or leave stale errors."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    held=[];mode='hold';errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def result(route):
        q=parse_qs(urlparse(route.request.url).query)
        offset=int(q['offset'][0]);size=int(q['limit'][0]);base=1000 if q.get('user_id')==['2'] else 0
        route.fulfill(json={'total':205,'items':[{'id':base+i,'user_id':2 if base else 1} for i in range(offset,min(205,offset+size))],'summary':{}})
    def listing(route):
        q=parse_qs(urlparse(route.request.url).query)
        if q['offset']==['200']:
            if mode=='hold':held.append(route);return
            if mode=='changed':route.fulfill(json={'total':204,'items':[],'summary':{}});return
        result(route)
    page.route('**/api/v1/ads?*',listing)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#adsPageSizeMenu summary').click()
    with page.expect_request('**/api/v1/ads?*offset=200*'):
        page.locator('[data-ads-size=All]').click()
    page.fill('#adsFilters [name=user_id]','2')
    with page.expect_request('**/api/v1/ads?*offset=200*'):
        page.locator('#adsFilters [type=submit]').click()
    page.wait_for_timeout(50)
    assert len(held)==2
    result(held.pop())
    expect(page.locator('#adsTable tbody tr')).to_have_count(205)
    expect(page.locator('#adsTable tbody [data-ads-field=id]').first).to_have_text('1000',use_inner_text=True)
    held.pop().fulfill(status=503,json={'detail':'obsolete batch'})
    page.wait_for_load_state('networkidle')
    expect(page.locator('#adsError')).to_be_empty()
    mode='changed';page.locator('#adsRefresh').click()
    expect(page.locator('#adsError')).to_contain_text('数据已变化')
    expect(page.locator('#adsTable tbody tr')).to_have_count(205)
    mode='normal';page.locator('#adsRetry').click()
    expect(page.locator('#adsError')).to_be_empty()
    mode='hold'
    with page.expect_request('**/api/v1/ads?*offset=200*'):
        page.locator('#adsRefresh').click()
    page.evaluate("location.hash='dashboard'")
    page.locator('#adsTable').wait_for(state='detached')
    held.pop().fulfill(status=503,json={'detail':'departed batch'})
    page.wait_for_load_state('networkidle')
    assert not errors,errors
    assert page.locator('#adsError').count()==0
    browser.close()
print('PASS: All batch filter races, changing total, retry and departed response')
