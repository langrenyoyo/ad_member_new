"""Delayed member editor responses and saves, with browser-only API fixtures."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page()
    rows=[{'id':9200+i,'username':f'fixture-{i}','name':f'original-{i}','status':1} for i in range(2)]
    reads=[];writes=[];lists=[];errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/api/auth/login',lambda r:r.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}}))
    def listing(route):
        lists.append(route.request.url)
        route.fulfill(json={'total':2,'items':rows})
    def detail(route):
        (reads if route.request.method=='GET' else writes).append(route)
    page.route('**/api/v1/members?*',listing)
    page.route('**/api/v1/members/920*',detail)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    def settle():page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    def click_edit(index=0):
        with page.expect_request(f'**/api/v1/members/{9200+index}'):
            page.locator(f'[data-edit="{9200+index}"]').click()
        settle()
    def navigate(suffix):
        with page.expect_request('**/api/v1/members?*'):
            page.evaluate('(suffix)=>location.hash="members"+suffix',suffix)
        page.wait_for_function('!document.querySelector("#content").hasAttribute("aria-busy")')
    def open_edit(index=0):
        click_edit(index);reads.pop().fulfill(json=rows[index])
        page.locator('#modal').wait_for(state='visible')
    def submit():
        with page.expect_request('**/api/v1/members/920*'):
            page.locator('#editorForm').evaluate('f=>{f.requestSubmit();f.requestSubmit();}')
        settle()

    # A late read from another scope must not open or repurpose the editor.
    click_edit();late=reads.pop();navigate('?agent_id=6200')
    late.fulfill(json=rows[0]);settle();assert page.locator('#modal').is_hidden()
    # Two overlapping opens resolve in the opposite order: latest selection wins.
    click_edit(0);first=reads.pop();click_edit(1);second=reads.pop()
    second.fulfill(json=rows[1]);page.locator('#modal').wait_for(state='visible')
    first.fulfill(json=rows[0]);settle()
    assert page.locator('#formFields [name=username]').input_value()=='fixture-1'
    page.locator('#closeModal').click()

    # Duplicate submits are suppressed; failure retains input and allows retry.
    open_edit();page.fill('#formFields [name=name]','changed')
    submit();assert len(writes)==1
    assert page.locator('#editorForm [type=submit]').is_disabled()
    assert page.locator('#editorForm [type=reset]').is_disabled()
    assert page.locator('#formFields [name=name]').is_disabled()
    writes.pop().fulfill(status=403,json={'detail':'fixture denied'})
    page.locator('.member-edit-error').get_by_text('fixture denied').wait_for()
    assert page.locator('#formFields [name=name]').input_value()=='changed'
    assert page.locator('#editorForm [type=submit]').is_enabled()
    submit();assert len(writes)==1 and writes[0].request.post_data_json=={'name':'changed'}
    writes.pop().fulfill(json={**rows[0],'name':'changed'})
    page.locator('#modal').wait_for(state='hidden')
    page.wait_for_function('!document.querySelector("#content").hasAttribute("aria-busy")')

    # Completion of a closed form must not close or clear a newly opened record.
    open_edit();page.fill('#formFields [name=name]','pending');submit();old_save=writes.pop()
    page.locator('#closeModal').click();open_edit(1)
    page.fill('#formFields [name=name]','new draft')
    old_save.fulfill(json=rows[0]);settle()
    assert page.locator('#modal').is_visible()
    assert page.locator('#formFields [name=name]').input_value()=='new draft'
    assert page.locator('#editorForm [type=submit]').is_enabled()
    assert page.locator('#editorForm').get_attribute('aria-busy') is None
    page.locator('#closeModal').click()

    # Navigating while saving closes the form; its response cannot refresh new scope.
    open_edit();page.fill('#formFields [name=name]','navigation');submit();old_save=writes.pop()
    navigate('?agent_id=6201');before=len(lists)
    old_save.fulfill(json=rows[0]);settle()
    assert page.locator('#modal').is_hidden() and len(lists)==before
    assert not errors,errors
    browser.close()
print('Member editor lifecycle: stale reads, latest selection, duplicate save, 403 retry, reopened form and navigation isolation passed')
