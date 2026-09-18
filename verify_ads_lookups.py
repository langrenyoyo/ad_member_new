"""Ad lookup paging, special text, clearing, ID races and disposal."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    requests=[];held=[];reads=[];errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def listing(route):
        reads.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':1,'items':[{'id':1,'game_name':'Game <>&'}],'summary':{}})
    def lookup(route):
        q=parse_qs(urlparse(route.request.url).query);requests.append(q)
        assert route.request.method=='GET' and route.request.headers.get('authorization','').startswith('Bearer ')
        if q.get('id')==['7200']:
            held.append(route);return
        rows=[{'id':7201+i,'name':f'Game {i:02d} <>&'} for i in range(12)]
        if q.get('id'):rows=[r for r in rows if str(r['id'])==q['id'][0]]
        if q.get('q'):rows=[r for r in rows if q['q'][0] in r['name']]
        offset=int(q['offset'][0])
        route.fulfill(json={'total':len(rows),'items':rows[offset:offset+10]})
    page.route('**/api/v1/ads?*',listing)
    page.route('**/api/v1/member-filter-options/**',lookup)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    game=page.locator('[data-ads-lookup=game_name]');game.click()
    expect(page.locator('.sp_result_area:visible li[pkey]')).to_have_count(10)
    game.press('ArrowRight')
    page.locator('.sp_result_area:visible li[pkey="7212"]').click()
    expect(game).to_have_value('Game 11 <>&')
    with page.expect_response('**/api/v1/ads?*'):
        page.locator('#adsFilters [type=submit]').click()
    assert reads[-1]['game_id']==['7212'] and 'game_name' not in reads[-1]
    page.evaluate('renderAds()')
    expect(game).to_have_value('Game 11 <>&')
    for scenario in ['success','failure','clear']:
        with page.expect_request('**/member-filter-options/games?*id=7200*'):
            page.evaluate("adsState.filters={game_id:'7200'};renderAds()")
        game.click();page.locator('.sp_result_area:visible li[pkey="7201"]').click()
        if scenario=='clear':game.locator('..').locator('.sp_clear_btn').click()
        if scenario=='failure':held.pop().fulfill(status=503,json={'detail':'old failure'})
        else:held.pop().fulfill(json={'total':1,'items':[{'id':7200,'name':'Old name'}]})
        page.wait_for_load_state('networkidle')
        expect(game).to_have_value('' if scenario=='clear' else 'Game 00 <>&')
        expect(page.locator('#adsFilters input[name=game_id]')).to_have_value('' if scenario=='clear' else '7201')
    page.locator('[data-ads-search=game_name]').click()
    expect(game).to_have_value('Game <>&')
    game.locator('..').locator('.sp_clear_btn').click()
    page.locator('#adsFilters input[name=parent_id]').click()
    with page.expect_response('**/api/v1/ads?*'):
        page.locator('#adsFilters [type=submit]').click()
    assert 'game_name' not in reads[-1] and 'game_id' not in reads[-1]
    game.click();game.fill('no match');game.press('x');game.press('Backspace')
    page.locator('.sp_result_area:visible').get_by_text('无查询结果',exact=True).wait_for()
    page.evaluate("location.hash='dashboard'")
    page.wait_for_function('memberLookupEntries.length===0')
    assert page.locator('.sp_result_area').count()==0 and not errors,errors
    browser.close()
print('PASS: ad lookup paging, IDs, literal names, stale success/failure, clearing, empty state and disposal')
