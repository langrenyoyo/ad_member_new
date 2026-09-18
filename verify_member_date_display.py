"""Validate rendered member timestamps independently of browser timezone."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch()
    for timezone in ['Asia/Shanghai','America/Los_Angeles']:
        page=browser.new_page(timezone_id=timezone)
        page.route('**/api/v1/members?*',lambda route:route.fulfill(json={'total':1,'items':[{'id':9000,'username':'date-fixture','game_id':1,'created_at':'2026-01-09T16:00:00','status':1}]}))
        page.goto('http://127.0.0.1:3000/#members')
        page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
        page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
        page.get_by_text('2026-01-10 00:00:00',exact=True).wait_for()
        page.fill('[data-mf=create_time]','2026-01-10')
        with page.expect_request(lambda request:'/api/v1/members?' in request.url and 'create_time=2026-01-10' in request.url):
            page.locator('#memberFilterSubmit').click()
        page.get_by_text('2026-01-10 00:00:00',exact=True).wait_for()
        page.close()
    browser.close()
print('Member timestamp display and date query passed in Beijing and Los Angeles browser timezones')
