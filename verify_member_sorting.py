"""Member header sort must reach the API before pagination, preserving filters/scope."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

rows=[{'id':i+1,'username':f'sort-fixture-{i+1}','game_id':1,'coin':25-i,'coin_user':i,'freeze_coin':i/10,'game_addiction_time':f'2026-02-{25-i:02d} 12:00:00','created_at':f'2026-01-{i+1:02d}T00:00:00Z'} for i in range(25)]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();queries=[]
    def respond(route):
        q=parse_qs(urlparse(route.request.url).query);queries.append(q)
        sort=q.get('sort',['id'])[0];ordered=sorted(rows,key=lambda row:row[sort],reverse=q.get('order',['desc'])[0]=='desc')
        offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['20'])[0])
        route.fulfill(json={'total':len(rows),'items':ordered[offset:offset+limit]})
    page.route('**/api/v1/members?*',respond)
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-member-sort=coin]').wait_for()
    page.fill('[data-mf=username]','sort-fixture');page.locator('#memberFilterSubmit').click()
    page.wait_for_function("document.querySelector('#content').getAttribute('aria-busy')===null")
    page.locator('#nextPage').click();page.get_by_text('sort-fixture-15',exact=True).wait_for()
    page.locator('.member-columns summary').click();page.locator('[data-member-column=game_addiction_time]').check()
    page.locator('.member-columns summary').focus();page.keyboard.press('Escape')
    for key in ['coin','coin_user','freeze_coin','created_at','game_addiction_time','id']:
        with page.expect_response(lambda r:'/api/v1/members?' in r.url):page.locator(f'[data-member-sort={key}]').click()
        page.wait_for_function("document.querySelector('#content').getAttribute('aria-busy')===null")
        assert queries[-1]['sort']==[key] and queries[-1]['order']==['asc'] and queries[-1]['offset']==['0']
        assert queries[-1]['agent_id']==['9000'] and queries[-1]['username']==['sort-fixture']
        assert page.locator(f'th[data-field={key}]').get_attribute('aria-sort')=='ascending'
        with page.expect_response(lambda r:'/api/v1/members?' in r.url):page.locator(f'[data-member-sort={key}]').click()
        page.wait_for_function("document.querySelector('#content').getAttribute('aria-busy')===null")
        assert queries[-1]['order']==['desc']
    assert page.locator('tbody tr').first.locator('td').nth(1).inner_text()=='25'
    browser.close()
print('Member sorting: six fields, both directions, page reset and retained filter/agent passed')
