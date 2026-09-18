"""Validate displayed filter values against actual list/export requests using fixtures."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(accept_downloads=True)
    page.set_default_timeout(10000)
    queries=[]
    def ads(route):
        queries.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':0,'items':[],'summary':{}})
    page.route('**/api/v1/ads?*',ads)
    page.route('**/api/v1/member-filter-options/agents?*',lambda r:r.fulfill(json={'total':1,'items':[{'id':6301,'name':'代理 <>&'}]}))
    page.route('**/api/v1/member-filter-options/games?*',lambda r:r.fulfill(json={'total':1,'items':[{'id':7301,'name':'游戏 <>&'}]}))
    exports=[]
    def export(route):
        exports.append(parse_qs(urlparse(route.request.url).query))
        assert route.request.headers.get('authorization','').startswith('Bearer ')
        route.fulfill(content_type='text/csv',body='id\n')
    page.route('**/api/v1/ads/export?*',export)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#adsSearchToggle').wait_for()
    assert queries[0]['is_fu']==['0']
    page.locator('[data-ads-lookup=agent_name]').click()
    expect(page.locator('.sp_result_area:visible li[pkey="6301"]')).to_have_text('代理 <>&')
    page.locator('.sp_result_area:visible li[pkey="6301"]').click()
    page.locator('[data-ads-lookup=game_name]').click()
    page.locator('.sp_result_area:visible li[pkey="7301"]').click()
    page.select_option('#adsFilters [name=is_fu]','1')
    page.fill('#adsFilters [name=estimate_income_min]','0.25')
    page.fill('#adsFilters [name=estimate_income_max]','3')
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=submit]').click()
    expected={'agent_id':'6301','game_id':'7301','is_fu':'1','estimate_income_min':'0.25','estimate_income_max':'3'}
    assert all(queries[-1][k]==[v] for k,v in expected.items())
    assert 'coin_min' not in queries[-1] and 'coin_max' not in queries[-1]
    page.evaluate('renderAds()')
    expect(page.locator('#adsFilters [name=agent_id]')).to_have_value('6301')
    expect(page.locator('#adsFilters [name=is_fu]')).to_have_value('1')
    expect(page.locator('#adsFilters [name=estimate_income_min]')).to_have_value('0.25')
    expect(page.locator('#adsFilters [name=estimate_income_max]')).to_have_value('3')
    page.locator('#adsExportToggle').click()
    with page.expect_download():
        page.locator('[data-ads-export=csv]').click()
    assert all(queries[-1][k]==[v] for k,v in expected.items())
    assert queries[-1]['offset']==['0'] and queries[-1]['limit']==['200']
    with page.expect_download():
        page.evaluate('downloadAds()')
    assert all(exports[-1][k]==[v] for k,v in expected.items())
    assert 'coin_min' not in exports[-1] and 'coin_max' not in exports[-1]
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=reset]').click()
    assert queries[-1]['is_fu']==['0'] and 'agent_id' not in queries[-1]
    assert 'estimate_income_min' not in queries[-1] and 'estimate_income_max' not in queries[-1]
    expect(page.locator('#adsFilters [name=agent_id]')).to_have_value('')
    browser.close()
print('PASS: option labels/IDs, initial/reset request defaults, restored fields and authenticated export filters')
