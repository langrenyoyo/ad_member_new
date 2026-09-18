"""Synthetic browser verification for the dedicated agent create/edit form."""
import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={"width":1280,"height":900})
    writes=[]
    row={"id":7,"parent_id":0,"name":"Fixture agent","user_name":"fixture-user","avatar":"","user_id":11,"role_id":22,"security_key":"fixture-key","status":1,"game_ad_status":0,"ht_status":1,"is_gx":0}
    def route_handler(route):
        request=route.request;url=urlparse(request.url);path=url.path.removeprefix('/api/').removeprefix('v1/').lstrip('/');path=path.split('?')[0]
        if path=='auth/login': route.fulfill(json={"access_token":"fixture","user":{"username":"fixture"}});return
        if request.method!='GET':
            writes.append({"method":request.method,"path":path,"body":request.post_data_json})
            route.fulfill(status=201 if request.method=='POST' else 200,json={**row,**request.post_data_json});return
        if path=='agents': route.fulfill(json={"items":[row],"total":1,"permissions":{"create":True,"edit":True,"delete":True,"oss":True,"batch_status":True,"dashboard":True}});return
        if path=='agents/7': route.fulfill(json=row);return
        if path.startswith('member-filter-options/agents'): route.fulfill(json={"items":[{"id":7,"name":"Fixture agent"},{"id":8,"name":"Parent agent"}],"total":2});return
        route.fulfill(json={"items":[],"total":0})
    page.route('**/api/**',route_handler)
    page.goto('http://127.0.0.1:3000/#agents')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#agentList tbody tr').wait_for()
    page.locator('#agentCreate').click()
    expect(page.locator('#modal')).to_be_visible();expect(page.locator('.agent-form-fields')).to_be_visible()
    page.screenshot(path='visual-baseline/verified/agent-form-1280.png',full_page=True)
    assert page.locator('.agent-form-field').count()==12
    page.locator('#editorForm [name=name]').fill('Created agent');page.locator('#editorForm [name=user_id]').fill('44');page.locator('#editorForm [name=status]').select_option('0');page.locator('#editorForm [name=password]').fill('New-Password-123')
    page.locator('#editorForm').evaluate('f=>f.requestSubmit()')
    page.wait_for_function('document.querySelector("#modal").hidden')
    assert writes[-1]=={"method":"POST","path":"agents","body":{"parent_id":0,"name":"Created agent","user_name":"","password":"New-Password-123","avatar":"","user_id":44,"security_key":"","status":0,"game_ad_status":0,"ht_status":0,"is_gx":0}}, writes[-1]
    page.locator('[data-edit="7"]').click();expect(page.locator('.agent-form-fields')).to_be_visible()
    assert page.locator('#editorForm [name=password]').input_value()==''
    page.locator('#editorForm [name=name]').fill('Updated agent');page.locator('#editorForm').evaluate('f=>f.requestSubmit()')
    page.wait_for_function('document.querySelector("#modal").hidden')
    assert writes[-1]=={"method":"PATCH","path":"agents/7","body":{"parent_id":0,"name":"Updated agent","user_name":"fixture-user","avatar":"","user_id":11,"role_id":22,"security_key":"fixture-key","status":1,"game_ad_status":0,"ht_status":1,"is_gx":0}}
    page.locator('#agentCreate').click();page.locator('#editorForm [name=name]').fill(' ');page.locator('#editorForm').evaluate('f=>f.requestSubmit()');expect(page.locator('.agent-form-error')).to_have_text('主体名称不能为空')
    assert len(writes)==2
    print(json.dumps({"passed":True,"writes":len(writes),"fields":12}))
    browser.close()
