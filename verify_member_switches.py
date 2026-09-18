"""Main member switches: isolated browser responses, no business database writes."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page()
    row={'id':9200,'username':'switch-fixture','status':0,'is_white':0,'exchange_enable':0}
    writes=[];held=[];alerts=[];reads=[]
    def listing(route):
        reads.append(route.request.url);route.fulfill(json={'total':1,'items':[row]})
    def patch(route):
        assert route.request.method=='PATCH'
        writes.append(route.request.post_data_json);held.append(route)
    page.route('**/api/v1/members?*',listing)
    page.route('**/api/v1/members/9200',patch)
    page.on('dialog',lambda d:(alerts.append(d.message),d.accept()))
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-switch[data-toggle]').wait_for()
    page.locator('.member-columns summary').click();page.locator('[data-member-column=exchange_enable]').check()
    page.locator('.member-columns summary').click()
    for field,selector in [('status','[data-toggle]'),('is_white','[data-white]'),('exchange_enable','[data-member-exchange]')]:
        button=page.locator('.member-switch'+selector)
        before=len(writes)
        button.click();button.evaluate('e=>e.dispatchEvent(new MouseEvent("click",{bubbles:true}))')
        page.wait_for_timeout(100)
        assert button.is_disabled() and len(writes)==before+1
        assert writes[-1]=={field:1} and button.get_attribute('aria-checked')=='false'
        held.pop().fulfill(status=403,json={'detail':'switch denied'})
        page.wait_for_function('(s)=>!document.querySelector(s).disabled',arg='.member-switch'+selector)
        assert button.get_attribute('aria-checked')=='false' and alerts[-1]=='switch denied'
        button.click();page.wait_for_timeout(100)
        row[field]=1;held.pop().fulfill(json=row)
        page.wait_for_function('(s)=>document.querySelector(s)?.getAttribute("aria-checked")==="true"',arg='.member-switch'+selector)
        assert not page.locator('.member-switch'+selector).is_disabled()
    button=page.locator('.member-switch[data-toggle]');button.click();page.wait_for_timeout(100)
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    count=len(reads);held.pop().fulfill(json={**row,'status':0});page.wait_for_load_state('networkidle')
    assert page.locator('.agent-panel').is_visible() and len(reads)==count
    assert len(alerts)==3
    browser.close()
print('Member switches: three field mappings, duplicate guard, denied retry, success refresh and navigation passed')
