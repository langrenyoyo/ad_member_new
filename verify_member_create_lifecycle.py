"""Isolated member creation failure/retry and duplicate-submit check."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();requests=[]
    page.route('**/api/auth/login',lambda r:r.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}}))
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':0,'items':[]}))
    page.route('**/api/v1/members',lambda r:requests.append(r))
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#createButton').click()
    for key,value in {'username':'new-fixture','name':'Fixture','receive_name':'Recipient','password':'Member-123','pay_password':'Payment-123'}.items():
        page.fill(f'#editorForm [name={key}]',value)
    page.locator('#editorForm').evaluate('f=>{f.requestSubmit();f.requestSubmit();}')
    page.wait_for_timeout(150)
    assert len(requests)==1, len(requests)
    page.once('dialog',lambda d:d.accept())
    requests.pop().fulfill(status=409,json={'detail':'fixture conflict'})
    page.wait_for_function('!document.querySelector("#editorForm").hasAttribute("aria-busy")')
    assert page.locator('#editorForm [name=username]').input_value()=='new-fixture'
    page.locator('#editorForm [type=submit]').click();page.wait_for_timeout(150)
    assert len(requests)==1
    requests.pop().fulfill(status=201,json={'id':9200})
    page.locator('#modal').wait_for(state='hidden')
    page.locator('#createButton').click()
    for key,value in {'username':'late-fixture','name':'Fixture','receive_name':'Recipient','password':'Member-123','pay_password':'Payment-123'}.items():
        page.fill(f'#editorForm [name={key}]',value)
    page.locator('#editorForm [type=submit]').click();page.wait_for_timeout(150)
    late=requests.pop()
    page.locator('#closeModal').click();page.locator('#createButton').click()
    page.fill('#editorForm [name=username]','replacement')
    late.fulfill(status=201,json={'id':9201});page.wait_for_timeout(150)
    assert page.locator('#modal').is_visible()
    assert page.locator('#editorForm [name=username]').input_value()=='replacement'
    assert page.locator('#editorForm [type=submit]').is_enabled()
    browser.close()
print('Member create: duplicate submit suppressed, failure preserves draft, retry succeeds')
