"""Relation editor lifecycle using browser fixtures; no reference writes."""
from playwright.sync_api import sync_playwright

row={'id':9200,'username':'关系测试','game_id':7200,'parent_id':11,'ht_id':22,'ht_top_id':33,'status':1}
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    writes=[];held=[];mode='deny'
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    def detail(route):
        if route.request.method=='GET':route.fulfill(json=row);return
        writes.append(route.request.post_data_json)
        if mode=='deny':route.fulfill(status=403,json={'detail':'无修改权限'})
        elif mode=='hold':held.append(route)
        else:row.update(route.request.post_data_json);route.fulfill(json=row)
    page.route('**/api/v1/members/9200',detail)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-member-rebind]').click()
    dialog=page.locator('#memberRebindDialog')
    page.wait_for_function("!document.querySelector('#memberRebindDialog [type=submit]').disabled")
    assert dialog.locator('[name=id]').is_disabled()
    assert dialog.locator('[name=id]').input_value()=='9200'
    assert [dialog.locator(f'[name={key}]').input_value() for key in ('parent_id','ht_id','ht_top_id')]==['11','22','33']
    dialog.locator('[name=parent_id]').fill('55');dialog.locator('[type=reset]').click()
    assert dialog.locator('[name=parent_id]').input_value()=='11'
    dialog.locator('[name=ht_id]').fill('1.5');dialog.locator('[type=submit]').click()
    assert dialog.get_by_role('alert').inner_text()=='请输入有效的整数ID' and not writes
    dialog.locator('[name=parent_id]').fill('0');dialog.locator('[name=ht_id]').fill('66');dialog.locator('[name=ht_top_id]').fill('77')
    dialog.locator('[type=submit]').click();dialog.get_by_text('无修改权限',exact=True).wait_for()
    assert dialog.locator('[name=ht_id]').input_value()=='66'
    assert writes==[{'parent_id':0,'ht_id':66,'ht_top_id':77}]
    mode='hold';dialog.locator('[type=submit]').click()
    dialog.locator('form').evaluate('f=>f.requestSubmit()')
    assert len(writes)==2 and dialog.locator('[type=reset]').is_disabled()
    held.pop().fulfill(json={**row,**writes[-1]});dialog.wait_for(state='detached')
    page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    page.locator('[data-member-rebind]').click()
    page.wait_for_function("!document.querySelector('#memberRebindDialog [type=submit]').disabled")
    dialog.locator('[type=submit]').click()
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    assert dialog.count()==0
    held.pop().fulfill(json=row);page.wait_for_load_state('networkidle')
    assert page.locator('.agent-panel').is_visible()
    browser.close()
print('Member rebind: prefill, disabled ID, reset, integer validation, denied save, retry, single pending write and navigation passed')
