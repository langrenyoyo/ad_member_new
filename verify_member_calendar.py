"""Member calendar presets use Beijing dates and keep request scope."""
from datetime import datetime,UTC
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(timezone_id='America/Los_Angeles');queries=[]
    page.clock.install(time=datetime(2026,1,10,18,tzinfo=UTC))
    def respond(route):
        queries.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':1,'items':[{'id':9200,'username':'日期会员','status':1}]})
    page.route('**/api/v1/members?*',respond)
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    field=page.locator('[data-mf=create_time]');field.wait_for()
    def ready():page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    field.click();page.locator('.daterangepicker:visible').wait_for()
    page.locator('.daterangepicker:visible [data-range-key="今天"]').click()
    assert field.input_value()=='2026-01-11 00:00:00 - 2026-01-11 23:59:59'
    page.locator('#memberFilterSubmit').click();ready()
    assert queries[-1]['create_time']==['2026-01-11 00:00:00 - 2026-01-11 23:59:59']
    assert queries[-1]['agent_id']==['9000']
    assert page.locator('.daterangepicker').count()==0
    field.click();page.locator('.daterangepicker:visible [data-range-key="昨天"]').click()
    assert field.input_value()=='2026-01-10 00:00:00 - 2026-01-10 23:59:59'
    field.click();page.keyboard.press('Escape')
    assert page.locator('.daterangepicker:visible').count()==0
    assert field.input_value()=='2026-01-10 00:00:00 - 2026-01-10 23:59:59'
    page.locator('#memberFilterReset').click();ready()
    assert 'create_time' not in queries[-1] and field.input_value()==''
    field.click();page.locator('.daterangepicker:visible').wait_for()
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    assert page.locator('.daterangepicker').count()==0
    browser.close()
print('Member calendar: Beijing today/yesterday in Los Angeles, scoped query, Escape, reset and lifecycle passed')
