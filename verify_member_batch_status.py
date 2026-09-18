"""Batch status browser requests with isolated data and delayed responses."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();writes=[];lists=[]
    rows=[{'id':9200+i,'username':f'fixture-{i}','status':1} for i in range(2)]
    page.route('**/api/auth/login',lambda r:r.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}}))
    def listing(r):lists.append(r.request.url);r.fulfill(json={'total':2,'items':rows})
    page.route('**/api/v1/members?*',listing)
    page.route('**/api/v1/members/batch-status*',lambda r:writes.append(r))
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    menu=page.locator('.member-batch-menu');menu.wait_for(state='attached')
    assert menu.is_hidden()
    # Exercise the dormant handler with an explicit test-only capability fixture.
    # This is not evidence that the reference exposes this menu to this account.
    page.evaluate("()=>{const reveal=()=>document.querySelectorAll('.member-batch-menu').forEach(e=>e.hidden=false);reveal();new MutationObserver(reveal).observe(document.querySelector('.topbar .toolbar'),{childList:true});}")
    assert menu.locator('summary').get_attribute('aria-disabled')=='true'
    page.locator('[data-select="9200"]').check();menu.locator('summary').click()
    menu.locator('[data-member-batch-status="0"]').click();page.wait_for_timeout(100)
    assert len(writes)==1 and writes[0].request.post_data_json=={'ids':[9200],'status':0}
    assert menu.locator('[data-member-batch-status="1"]').is_disabled()
    page.once('dialog',lambda d:d.accept());writes.pop().fulfill(status=503,json={'detail':'fixture retry'})
    page.wait_for_function('!document.querySelector("[data-member-batch-status]").disabled')
    assert page.locator('[data-select="9200"]').is_checked()
    page.locator('[data-select="9201"]').check();menu.locator('summary').click()
    menu.locator('[data-member-batch-status="1"]').click();page.wait_for_timeout(100)
    assert writes[0].request.post_data_json=={'ids':[9200,9201],'status':1}
    writes.pop().fulfill(json={'updated':2})
    page.wait_for_function('document.querySelectorAll("[data-select]:checked").length===0')
    page.locator('[data-select="9200"]').check();menu.locator('summary').click()
    menu.locator('[data-member-batch-status="0"]').click();page.wait_for_timeout(100)
    late=writes.pop();page.evaluate('location.hash="members?agent_id=991001"')
    page.wait_for_function('!document.querySelector("#content").hasAttribute("aria-busy")')
    count=len(lists);late.fulfill(json={'updated':1});page.wait_for_timeout(100)
    assert len(lists)==count
    page.locator('[data-select="9200"]').check();menu.locator('summary').click()
    menu.locator('[data-member-batch-status="1"]').click();page.wait_for_timeout(100)
    assert 'agent_id=991001' in writes[0].request.url
    writes.pop().fulfill(json={'updated':1})
    page.wait_for_function('document.querySelectorAll("[data-select]:checked").length===0')
    browser.close()
print('Member batch: selection, payload, pending lock, retry and stale-scope completion passed')
