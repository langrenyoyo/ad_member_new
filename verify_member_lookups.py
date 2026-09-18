"""Member lookup selection, paging, ID query, reset and disposal fixtures."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    reads=[];options=[];errors=[];mode='normal'
    page.on('pageerror',lambda e:errors.append(str(e)))
    def members(route):
        reads.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':1,'items':[{'id':9200,'username':'fixture','status':1,'game_id':7200,'game_name':'Game 00'}]})
    def lookup(route):
        assert route.request.method=='GET'
        assert route.request.headers.get('authorization','').startswith('Bearer ')
        if mode=='error':
            route.abort();return
        q=parse_qs(urlparse(route.request.url).query);options.append(q)
        agent='/agents?' in route.request.url
        rows=[{'id':6200+i if agent else 7200+i,'name':('Agent ' if agent else 'Game ')+f'{i:02d}'} for i in range(12)]
        if q.get('id'):rows=[r for r in rows if str(r['id'])==q['id'][0]]
        if q.get('q'):rows=[r for r in rows if q['q'][0] in r['name']]
        offset=int(q.get('offset',['0'])[0]);route.fulfill(json={'total':len(rows),'items':rows[offset:offset+10]})
    page.route('**/api/v1/members?*',members);page.route('**/api/v1/member-filter-options/**',lookup)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    game=page.locator('[data-member-lookup=game_name]');game.click()
    page.locator('.sp_result_area:visible .sp_results li').first.wait_for()
    assert page.locator('.sp_result_area:visible .sp_results li').count()==10
    page.locator('.sp_result_area:visible .sp_results li').first.click()
    assert page.locator('[data-mf=game_id]').input_value()=='7200'
    page.locator('[data-member-lookup=agent_name]').click()
    page.locator('.sp_result_area:visible .sp_results li').first.click()
    with page.expect_response('**/api/v1/member-filter-options/games?*id=7200*'):
        page.locator('#memberFilterSubmit').click()
    page.wait_for_function("document.querySelector('[data-member-lookup=game_name]')?.value==='Game 00'")
    assert reads[-1]['game_id']==['7200'] and reads[-1]['agent_id']==['6200']
    assert 'game_name' not in reads[-1] and 'agent_name' not in reads[-1]
    assert any(q.get('id')==['7200'] for q in options)
    with page.expect_response('**/api/v1/members?*game_name=*'):
        page.locator('[data-member-search-field=game_name]').first.click()
    assert reads[-1]['game_name']==['Game 00'] and 'game_id' not in reads[-1]
    assert reads[-1]['agent_id']==['6200']
    page.wait_for_function("document.querySelector('[data-mf=game_name]')?.value==='Game 00'")
    page.locator('#memberFilterReset').click()
    page.wait_for_function("document.querySelector('[data-member-lookup=game_name]')?.value===''")
    assert 'game_id' not in reads[-1] and 'agent_id' not in reads[-1]
    game=page.locator('[data-member-lookup=game_name]');game.click();game.fill('Game 11');game.press('1');game.press('Backspace')
    page.wait_for_function("document.querySelector('.sp_result_area:not([style*=\"display: none\"]) .sp_results')?.textContent.includes('Game 11')")
    page.locator('.sp_result_area:visible .sp_results li').first.click()
    assert page.locator('[data-mf=game_id]').input_value()=='7211'
    mode='error'
    with page.expect_event('requestfailed',predicate=lambda request:'/member-filter-options/games?' in request.url and 'does-not-exist' in request.url):
        game.click();game.fill('does-not-exist');game.press('x');game.press('Backspace')
    assert page.locator('[data-mf=game_id]').input_value()=='7211'
    page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    assert page.locator('.sp_result_area').count()==0 and not errors,errors
    browser.close()
print('Member lookups: authenticated requests, option page, selection IDs, label restoration, reset, search and disposal passed')
