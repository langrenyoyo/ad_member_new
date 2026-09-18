"""Coin form behavior against mocked read/write responses, no business writes."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});writes=[];held=[];mode='deny'
    row={'id':9200,'username':'金币会员','coin':12.5,'freeze_coin':3,'status':1}
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    def detail(route):
        if route.request.method=='GET':route.fulfill(json=row);return
        writes.append(route.request.post_data_json)
        if mode=='hold':held.append(route);return
        if mode=='deny':route.fulfill(status=403,json={'detail':'无修改权限'});return
        row.update(route.request.post_data_json);route.fulfill(json=row)
    page.route('**/api/v1/members/9200',detail)
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-coin]').click();dialog=page.locator('#memberCoinDialog');dialog.wait_for()
    page.wait_for_function("!document.querySelector('#memberCoinDialog [type=submit]').disabled")
    assert dialog.locator('[name=coin]').input_value()=='12.5'
    assert dialog.locator('[name=freeze_coin]').input_value()=='3'
    title=dialog.locator('header').bounding_box()
    page.mouse.move(title['x']+100,title['y']+20);page.mouse.down();page.mouse.move(title['x']+200,title['y']+80,steps=6);page.mouse.up()
    assert dialog.bounding_box()=={'x':660,'y':300,'width':800,'height':600}
    dialog.get_by_role('button',name='最大化',exact=True).click()
    assert dialog.bounding_box()['width']==1920
    assert dialog.locator('.member-coin-minimize').is_hidden()
    dialog.get_by_role('button',name='还原',exact=True).click()
    assert dialog.bounding_box()['width']==800
    assert dialog.bounding_box()['x']==660 and dialog.bounding_box()['y']==300
    dialog.locator('[name=coin]').fill('77.5')
    dialog.get_by_role('button',name='最小化',exact=True).click()
    assert dialog.bounding_box()=={'x':0,'y':1035,'width':180,'height':45}
    assert dialog.locator('form').is_hidden()
    assert page.locator('#refresh').is_enabled()
    dialog.get_by_role('button',name='还原',exact=True).click()
    assert dialog.bounding_box()['width']==800
    assert dialog.locator('[name=coin]').input_value()=='77.5'
    dialog.locator('[name=coin]').fill('99');dialog.locator('[type=reset]').click()
    assert dialog.locator('[name=coin]').input_value()=='12.5'
    dialog.locator('[name=freeze_coin]').fill('NaN');dialog.locator('[type=submit]').click()
    assert dialog.get_by_role('alert').inner_text()=='请输入有效的金币数值' and not writes
    dialog.locator('[name=coin]').fill('25.75');dialog.locator('[name=freeze_coin]').fill('4.5')
    dialog.locator('[type=submit]').click();dialog.get_by_text('无修改权限',exact=True).wait_for()
    assert dialog.locator('[name=coin]').input_value()=='25.75'
    mode='ok';dialog.locator('[type=submit]').click();dialog.wait_for(state='detached')
    assert writes[-1]=={'coin':25.75,'freeze_coin':4.5}
    page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    assert page.locator('td[data-field=coin] .member-card-value').inner_text()=='25.75'
    page.locator('[data-coin]').click();page.wait_for_function("!document.querySelector('#memberCoinDialog [type=submit]').disabled")
    page.keyboard.press('Escape');dialog.wait_for(state='detached')
    count=len(writes);page.locator('[data-coin]').click();page.wait_for_function("!document.querySelector('#memberCoinDialog [type=submit]').disabled")
    mode='hold';dialog.locator('[type=submit]').click()
    dialog.locator('form').evaluate('f=>f.requestSubmit()');assert len(writes)==count+1
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for();assert dialog.count()==0
    held[0].fulfill(json=row);page.wait_for_load_state('networkidle')
    assert page.locator('.agent-panel').is_visible()
    browser.close()
print('Member coins: prefill, reset, two-field validation/PATCH, denied save, success, cancel, duplicate guard and navigation passed')
