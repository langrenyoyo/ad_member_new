"""Click searches keep applied filters, sort, size and explicit agent scope."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

values={'username':'账号 <>&"%','parent_id':0,'game_name':'游戏甲','agent_name':'主体甲','name':'昵称甲','ip':'192.0.2.1'}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});queries=[]
    def respond(route):
        queries.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':30,'items':[{'id':9200,'status':1,'vip':0,**values}]})
    page.route('**/api/v1/members?*',respond)
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-columns').wait_for()
    def ready():page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    assert page.locator('[data-mf=vip] option').evaluate_all('els=>els.map(e=>e.value)')==['','0','1','2']
    page.select_option('[data-mf=vip]','1');page.locator('#memberFilterSubmit').click();ready()
    page.select_option('#memberPageSize','20');ready()
    page.locator('[data-member-sort=coin]').click();ready()
    page.locator('.member-columns summary').click()
    for key in ['parent_id','agent_name','name']:page.locator(f'[data-member-column={key}]').check()
    page.locator('.member-columns summary').focus();page.keyboard.press('Escape')
    page.locator('#memberSearchToggle').click()
    for key,value in values.items():
        page.locator('#nextPage').click();ready()
        assert queries[-1]['offset']==['20']
        page.locator(f'[data-member-search-field={key}]').click();ready()
        assert queries[-1][key]==[str(value)]
        assert queries[-1]['offset']==['0'] and queries[-1]['limit']==['20']
        assert queries[-1]['agent_id']==['9000'] and queries[-1]['vip']==['1']
        assert queries[-1]['sort']==['coin'] and queries[-1]['order']==['asc']
        assert page.locator(f'[data-mf={key}]').input_value()==str(value)
        assert page.locator('#memberFilters').is_hidden()
    page.locator('#memberViewToggle').click()
    page.locator('[data-member-search-field=vip] span').click();ready()
    assert queries[-1]['vip']==['0'] and queries[-1]['offset']==['0']
    assert queries[-1]['agent_id']==['9000'] and queries[-1]['limit']==['20']
    assert page.locator('[data-mf=vip]').input_value()=='0'
    assert page.locator('.member-card-table').count()==1
    page.locator('#memberSearchToggle').click();page.locator('#memberFilterReset').click();ready()
    assert 'vip' not in queries[-1]
    assert all(key not in queries[-1] for key in values)
    assert queries[-1]['agent_id']==['9000']
    browser.close()
print('Member click search: six text columns, VIP 0 in card view, reference options, escaping, retained scope/filter/sort/size and reset passed')
