"""Name cell searches survive form submit, refresh and authenticated export."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(accept_downloads=True)
    queries=[]
    def listing(route):
        queries.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':1,'items':[{'id':1,'game_name':'Game <>&','agent_name':'Agent 100%_','user_account':'Account <>&'}],'summary':{}})
    page.route('**/api/v1/ads?*',listing)
    page.route('**/api/v1/member-filter-options/games?*',lambda r:r.fulfill(json={'total':1,'items':[{'id':42,'name':'Other game'}]}))
    page.route('**/api/v1/member-filter-options/agents?*',lambda r:r.fulfill(json={'total':0,'items':[]}))
    exports=[]
    def export(route):
        assert route.request.headers.get('authorization','').startswith('Bearer ')
        exports.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(content_type='text/csv',body='id\n1\n')
    page.route('**/api/v1/ads/export?*',export)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#adsColumnsToggle').wait_for()
    expect(page.locator('th[data-ads-field=agent_name]')).to_be_hidden()
    page.locator('#adsColumnsToggle').click()
    page.locator('[data-ads-column=agent_name]').check()
    page.locator('#adsColumnsToggle').click()
    before=len(queries)
    page.locator('[data-ads-search=user_account]').click()
    page.wait_for_timeout(150)
    assert len(queries)==before
    for field,value in [('game_name','Game <>&'),('agent_name','Agent 100%_')]:
        with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
            page.locator(f'[data-ads-search={field}]').click()
        assert queries[-1][field]==[value]
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.evaluate('renderAds()')
    expect(page.locator('[data-ads-lookup=game_name]')).to_have_value('Game <>&')
    expect(page.locator('[data-ads-lookup=agent_name]')).to_have_value('Agent 100%_')
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=submit]').click()
    assert queries[-1]['game_name']==['Game <>&'] and queries[-1]['agent_name']==['Agent 100%_']
    page.locator('#adsExportToggle').click()
    with page.expect_download():
        page.locator('[data-ads-export=csv]').click()
    assert queries[-1]['game_name']==['Game <>&'] and queries[-1]['agent_name']==['Agent 100%_']
    with page.expect_download():
        page.evaluate('downloadAds()')
    assert exports[-1]['game_name']==['Game <>&'] and exports[-1]['agent_name']==['Agent 100%_']
    page.locator('[data-ads-lookup=game_name]').click()
    page.locator('.sp_result_area:visible li[pkey="42"]').click()
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=submit]').click()
    assert queries[-1]['game_id']==['42'] and 'game_name' not in queries[-1]
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=reset]').click()
    assert 'game_name' not in queries[-1] and 'agent_name' not in queries[-1]
    browser.close()
print('PASS: hidden agent, name search, inert account link, restored fields, submit, export, ID replacement and reset')
