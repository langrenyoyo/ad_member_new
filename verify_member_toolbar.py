"""Browser-only member selection, edit routing and filter visibility regression."""
from playwright.sync_api import sync_playwright

rows=[{'id':9000+i,'username':f'工具栏会员{i}','name':f'会员{i}','receive_name':'原收款姓名','game_id':1,'status':1} for i in range(3)]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();writes=[];reads=[];empty=False
    def members(route):route.fulfill(json={'total':0 if empty else 3,'items':[] if empty else rows})
    def detail(route):
        if route.request.method!='GET':writes.append({'method':route.request.method,'body':route.request.post_data_json})
        reads.append(route.request.url);route.fulfill(json=rows[1])
    page.route('**/api/v1/members?*',members);page.route('**/api/v1/members/9001',detail)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#memberSelectionEdit').wait_for()
    assert page.locator('.member-batch-menu').is_hidden()
    assert page.locator('#memberSelectionEdit').is_disabled()
    page.get_by_label('全选本页会员').check()
    assert page.locator('.member-batch-menu').is_hidden()
    assert page.locator('[data-select]:checked').count()==3 and page.locator('#memberSelectionEdit').is_disabled()
    page.get_by_label('全选本页会员').uncheck();page.locator('[data-select="9001"]').check()
    assert page.get_by_label('全选本页会员').evaluate('e=>e.indeterminate')
    page.locator('#memberSelectionEdit').click();page.locator('#modal').wait_for(state='visible')
    assert page.locator('#formFields [name=username]').is_visible()
    assert page.locator('#formFields [name=username]').input_value()=='工具栏会员1' and len(reads)==1
    page.locator('#closeModal').click();assert not writes
    page.locator('#memberSelectionEdit').click()
    page.locator('#formFields [name=name]').fill('修改后的会员名称')
    page.locator('#formFields [name=receive_name]').fill('新收款姓名')
    page.locator('#editorForm button[type=submit]').click()
    page.locator('#modal').wait_for(state='hidden')
    page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    assert writes==[{'method':'PATCH','body':{'name':'修改后的会员名称','receive_name':'新收款姓名'}}]
    page.fill('[data-mf=username]','尚未提交')
    page.locator('#memberSearchToggle').click();assert page.locator('#memberFilters').is_hidden()
    page.locator('#memberSearchToggle').click();assert page.locator('[data-mf=username]').input_value()=='尚未提交'
    page.locator('#memberSearchToggle').click();page.locator('#refresh').click()
    page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    assert page.locator('#memberFilters').is_hidden()
    assert page.locator('[data-select]:checked').count()==0 and page.locator('#memberSelectionEdit').is_disabled()
    empty=True;page.locator('#refresh').click();page.locator('.empty').wait_for()
    assert page.locator('#memberSelectionEdit').is_disabled()
    page.locator('#memberSearchToggle').click();assert page.locator('#memberFilters').is_visible()
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    assert page.locator('[data-member-toolbar]').count()==0
    browser.close()
print('Member toolbar: select all/partial, one-row edit, filter collapse, empty and route cleanup passed')
