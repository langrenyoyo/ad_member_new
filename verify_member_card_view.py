"""Member card mode shares column visibility, selection and working actions."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});reads=[];empty=False
    def members(route):
        reads.append(route.request.url)
        route.fulfill(json={'total':0 if empty else 30,'items':[] if empty else [{'id':9200,'username':'卡片会员','name':'隐藏昵称','receive_name':'收款姓名','status':1}]})
    page.route('**/api/v1/members?*',members)
    page.route('**/api/v1/members/9200',lambda r:r.fulfill(json={'id':9200,'username':'卡片会员','name':'隐藏昵称','receive_name':'收款姓名'}))
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#memberViewToggle').wait_for()
    def ready():page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    page.locator('[data-select="9200"]').check();count=len(reads)
    page.locator('#memberViewToggle').click()
    assert len(reads)==count and page.locator('thead').is_hidden()
    assert page.locator('td[data-field=id] .member-card-label').inner_text()=='Id'
    assert page.locator('td[data-field=receive_name] .member-card-value').inner_text()=='收款姓名'
    assert page.locator('[data-select="9200"]').is_checked()
    page.locator('td[data-field=id] .member-card-label').click()
    assert not page.locator('[data-select="9200"]').is_checked()
    page.locator('td[data-field=id] .member-card-value').click()
    assert page.locator('[data-select="9200"]').is_checked()
    page.locator('#memberSelectionEdit').click();page.locator('#modal').wait_for(state='visible')
    assert page.locator('#formFields [name=username]').input_value()=='卡片会员'
    page.locator('#closeModal').click()
    page.locator('.member-columns summary').click();page.locator('[data-member-column=name]').check()
    page.locator('.member-columns summary').focus();page.keyboard.press('Escape')
    assert page.locator('td[data-field=name] .member-card-value').is_visible()
    page.locator('#nextPage').click();ready()
    assert page.locator('.member-card-table').count()==1
    assert page.locator('#memberViewToggle').get_attribute('aria-pressed')=='true'
    page.locator('[data-member-search-field=username]').click();ready()
    assert 'username=' in reads[-1] and 'offset=0' in reads[-1]
    page.locator('#memberViewToggle').click()
    assert page.locator('thead').is_visible()
    assert page.locator('td[data-field=name] .member-card-label').is_hidden()
    page.locator('#memberViewToggle').click();empty=True;page.locator('#refresh').click();ready()
    assert page.locator('.empty').is_visible()
    page.locator('#memberViewToggle').click()
    assert page.locator('#memberViewToggle').get_attribute('aria-pressed')=='false'
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    assert page.locator('#memberViewToggle').count()==0
    browser.close()
print('Member cards: local toggle, field labels, selection/edit, columns, paging/search, empty and cleanup passed')
