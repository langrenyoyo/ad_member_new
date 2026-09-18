"""Reference member paging: sizes, wrap, jump, all rows and shrinking results."""
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});total=205;queries=[]
    def respond(route):
        query=parse_qs(urlparse(route.request.url).query);queries.append(query)
        offset=int(query['offset'][0]);limit=int(query['limit'][0])
        rows=[{'id':i+1,'username':f'fixture-{i}','game_id':1,'status':1} for i in range(total)]
        route.fulfill(json={'total':total,'items':rows[offset:offset+limit]})
    page.route('**/api/v1/members?*',respond)
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('tbody tr').first.wait_for()
    def ready():page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    assert queries[-1]['limit']==['10'] and page.locator('tbody tr').count()==10
    page.fill('[data-mf=username]','fixture');page.locator('#memberFilterSubmit').click();ready()
    page.locator('#prevPage').click();ready()
    assert queries[-1]['offset']==['200'] and page.locator('tbody tr').count()==5
    page.locator('#nextPage').click();ready();assert queries[-1]['offset']==['0']
    page.get_by_label('跳转页码').fill('3');page.get_by_label('跳转页码').press('Enter');ready()
    assert queries[-1]['offset']==['20']
    before=len(queries);page.get_by_label('跳转页码').fill('999');page.locator('#memberPageJump').click()
    assert len(queries)==before
    for size in [15,20,25,50]:
        page.select_option('#memberPageSize',str(size));ready()
        assert queries[-1]['limit']==[str(size)] and queries[-1]['offset']==['0']
        assert page.locator('tbody tr').count()==size
    page.select_option('#memberPageSize','All');ready()
    assert page.locator('tbody tr').count()==205
    assert queries[-2]['offset']==['0'] and queries[-1]['offset']==['200']
    assert page.locator('#nextPage').is_hidden()
    assert all(q.get('agent_id')==['9000'] and q.get('username')==['fixture'] for q in queries[1:])
    page.select_option('#memberPageSize','20');ready();total=40
    page.locator('#refresh').click();ready();page.locator('#nextPage').click();ready()
    assert page.locator('tbody tr').count()==20 and queries[-1]['offset']==['20']
    total=3;page.locator('#refresh').click();ready()
    assert queries[-1]['offset']==['0'] and page.locator('tbody tr').count()==3
    assert page.locator('#nextPage').is_hidden() and page.locator('#memberPageSize').is_hidden()
    total=0;page.locator('#refresh').click();ready()
    assert page.locator('.empty').is_visible() and page.locator('.member-pagination').is_hidden()
    browser.close()
print('Member paging: default 10, 15/20/25/50/All, wrap, jump, scope, full final page, shrinking and empty passed')
