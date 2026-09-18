"""Exercise member column choices with browser fixtures; no business writes."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920,'height':1080})
    reads = []
    def members(route):
        reads.append(route.request.url)
        route.fulfill(json={'total':40,'items':[{
            'id':9200, 'username':'列测试账号', 'parent_username':'上级账号甲',
            'agent_name':'主体甲', 'name':'昵称甲', 'status':1,
            'last_login_device_id':'device-actual', 'game_addiction_enable':1,
            'exchange_enable':0, 'last_login_time':'2026-09-16T00:00:00Z'
        }]})
    page.route('**/api/v1/members?*', members)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-columns').wait_for()
    def ready():
        page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    def choose(key, checked):
        menu=page.locator('.member-columns')
        if not menu.evaluate('e=>e.open'):
            menu.locator('summary').click()
        page.locator(f'[data-member-column="{key}"]').set_checked(checked)
    assert page.locator('th[data-field]:visible').count()==16
    assert page.locator('th[data-field="name"]').is_hidden()
    page.locator('[data-select="9200"]').check()
    for key in ['parent_username','agent_name','name','last_login_device_id','game_addiction_enable','exchange_enable','last_login_time']:
        choose(key,True)
    choose('username',False)
    assert page.locator('td[data-field="username"]').is_hidden()
    assert page.locator('td[data-field="parent_username"]').inner_text()=='上级账号甲'
    assert page.locator('td[data-field="last_login_device_id"]').inner_text()=='device-actual'
    assert page.locator('td[data-field="game_addiction_enable"]').inner_text()=='是'
    assert page.locator('td[data-field="exchange_enable"]').inner_text()=='否'
    assert '08:00:00' in page.locator('td[data-field="last_login_time"]').inner_text()
    assert page.locator('[data-select="9200"]').is_checked()
    assert page.locator('#memberSelectionEdit').is_enabled()
    assert len(reads)==1, 'Column toggles must not issue list requests'
    page.locator('.member-columns summary').focus();page.keyboard.press('Escape')
    assert not page.locator('.member-columns').evaluate('e=>e.open')
    page.locator('[data-member-sort="coin"]').click();ready()
    assert 'sort=coin' in reads[-1]
    assert page.locator('th[data-field="name"]').is_visible()
    assert page.locator('th[data-field="username"]').is_hidden()
    page.locator('#nextPage').click();ready()
    assert 'offset=10' in reads[-1]
    assert page.locator('th[data-field="name"]').is_visible()
    # The last visible column cannot be unchecked.
    for key in page.locator('[data-member-column]:checked').evaluate_all('els=>els.map(e=>e.dataset.memberColumn)'):
        if key!='id':choose(key,False)
    assert page.locator('[data-member-column="id"]').is_disabled()
    assert page.locator('th[data-field]:visible').count()==1
    page.evaluate("location.hash='agents'")
    page.locator('.agent-panel').wait_for()
    assert page.locator('.member-columns').count()==0
    browser.close()
print('Member columns: real fixture values, default visibility, selection, sorting, paging, minimum and cleanup passed')
