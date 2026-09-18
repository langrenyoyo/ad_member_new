"""Delayed ID restoration must never replace a newly selected lookup value."""
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();held=[];errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'items':[],'total':0}))
    def lookup(route):
        q=parse_qs(urlparse(route.request.url).query)
        if q.get('id')==['7200']:held.append(route)
        else:route.fulfill(json={'items':[{'id':7201,'name':'New game'}],'total':1})
    page.route('**/api/v1/member-filter-options/games?*',lookup)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-member-lookup=game_name]').wait_for()
    with page.expect_request('**/api/v1/member-filter-options/games?*id=7200*'):
        page.evaluate("state.memberFilters={game_id:'7200'};load()")
    game=page.locator('[data-member-lookup=game_name]');game.click()
    page.locator('.sp_result_area:visible li[pkey="7201"]').click()
    assert page.locator('[data-mf=game_id]').input_value()=='7201'
    with page.expect_response('**/api/v1/member-filter-options/games?*id=7200*'):
        held.pop().fulfill(json={'items':[{'id':7200,'name':'Old game'}],'total':1})
    page.wait_for_load_state('networkidle')
    assert game.input_value()=='New game',(game.input_value(),'stale restoration replaced new selection')
    assert page.locator('[data-mf=game_id]').input_value()=='7201'
    assert not errors,errors
    # A late failure from the old ID must not display an error over a new choice.
    for scenario in ('old-error','clear'):
        with page.expect_request('**/api/v1/member-filter-options/games?*id=7200*'):
            page.evaluate("state.memberFilters={game_id:'7200'};load()")
        game=page.locator('[data-member-lookup=game_name]');game.click()
        page.locator('.sp_result_area:visible li[pkey="7201"]').click()
        if scenario=='clear':
            game.locator('..').locator('.sp_clear_btn').click()
        with page.expect_response('**/api/v1/member-filter-options/games?*id=7200*'):
            if scenario=='old-error':held.pop().fulfill(status=500,json={'detail':'old lookup failed'})
            else:held.pop().fulfill(json={'items':[{'id':7200,'name':'Old game'}],'total':1})
        page.wait_for_load_state('networkidle')
        assert game.input_value()==('' if scenario=='clear' else 'New game')
        assert page.locator('[data-mf=game_id]').input_value()==('' if scenario=='clear' else '7201')
        assert page.get_by_text('加载数据时发生了错误！',exact=False).count()==0
        assert not errors,errors
    browser.close()
print('Member lookup races: late ID success/error and clear preserve current selection')
