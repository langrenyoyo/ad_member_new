"""Hold browser requests to exercise out-of-order success/failure and retry."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.set_default_timeout(10000)
    held=[]
    mode={'hold':False,'fail':False}
    def result(route):
        offset=int(parse_qs(urlparse(route.request.url).query)['offset'][0])
        route.fulfill(json={'total':35,'items':[{'id':1000+offset,'user_account':f'offset {offset}'}],'summary':{}})
    def respond(route):
        if mode['hold']:held.append(route)
        elif mode['fail']:route.fulfill(status=503,json={'detail':'fixture unavailable'})
        else:result(route)
    page.route('**/api/v1/ads?*',respond)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    first=page.locator('#adsTable tbody [data-ads-field=id]').first
    expect(first).to_have_text('1000',use_inner_text=True)
    mode['hold']=True
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-page="2"]').first.click()
    # Keep old pagination visible while the first request is pending.
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-page="4"]').first.click()
    page.wait_for_timeout(50)
    assert len(held)==2
    result(held.pop())
    expect(first).to_have_text('1030',use_inner_text=True)
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        result(held.pop())
    page.wait_for_timeout(100)
    expect(first).to_have_text('1030',use_inner_text=True)
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-page="1"]').first.click()
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-page="3"]').first.click()
    page.wait_for_timeout(50)
    assert len(held)==2
    result(held.pop())
    expect(first).to_have_text('1020',use_inner_text=True)
    held.pop().fulfill(status=503,json={'detail':'obsolete failure'})
    page.wait_for_timeout(100)
    expect(page.locator('#adsError')).to_have_text('')
    mode.update(hold=False,fail=True)
    page.locator('[data-ads-page="4"]').first.click()
    expect(page.locator('#adsError')).to_contain_text('fixture unavailable')
    mode['fail']=False
    page.locator('#adsRetry').click()
    expect(first).to_have_text('1030',use_inner_text=True)
    expect(page.locator('#adsError')).to_have_text('')
    mode['hold']=True
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-page="1"]').first.click()
    page.evaluate("location.hash='profile'")
    page.locator('#adsTable').wait_for(state='detached')
    page.wait_for_timeout(50)
    held.pop().fulfill(status=503,json={'detail':'departed failure'})
    page.wait_for_timeout(100)
    assert page.locator('#adsError').count()==0
    browser.close()
print('PASS: latest success wins, stale failure ignored, failed-page retry, route departure')
