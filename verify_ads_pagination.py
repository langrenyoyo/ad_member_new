"""Paginated fixture proves records past the first page remain reachable."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.set_default_timeout(10000)
    total=35
    requests=[]
    def respond(route):
        query=parse_qs(urlparse(route.request.url).query)
        requests.append(query)
        size=int(query['limit'][0]); offset=int(query['offset'][0])
        count=0 if query.get('user_id')==['999999'] else total
        route.fulfill(json={'total':count,'items':[{'id':1000+i,'user_id':2000+i,'parent_id':0,'user_account':f'fixture {i}'} for i in range(offset,min(count,offset+size))],'summary':{}})
    page.route('**/api/v1/ads?*',respond)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    first=page.locator('#adsTable tbody td[data-ads-field=id]').first
    expect(first).to_have_text('1000',use_inner_text=True)
    assert requests[0]['limit']==['10']
    page.locator('[data-ads-page="4"]').first.click()
    expect(first).to_have_text('1030',use_inner_text=True)
    assert page.locator('#adsTable tbody tr').count()==5
    assert requests[-1]['offset']==['30']
    page.locator('#adsPagination [aria-label="下一页"]').click()
    expect(first).to_have_text('1000',use_inner_text=True)
    page.locator('#adsPagination [aria-label="上一页"]').click()
    expect(first).to_have_text('1030',use_inner_text=True)
    page.locator('[data-ads-sort="estimate_income"]').click()
    expect(first).to_have_text('1000',use_inner_text=True)
    assert requests[-1]['sort']==['estimate_income'] and requests[-1]['order']==['desc']
    assert requests[-1]['offset']==['0']
    page.locator('#adsPageSizeMenu summary').click()
    page.locator('[data-ads-size="15"]').click()
    expect(first).to_have_text('1000',use_inner_text=True)
    expect(page.locator('#adsTable tbody tr')).to_have_count(15)
    assert requests[-1]['sort']==['estimate_income']
    page.fill('[aria-label="跳转页码"]','3')
    page.locator('[data-ads-jump]').click()
    expect(first).to_have_text('1030',use_inner_text=True)
    page.fill('#adsFilters [name=user_id]','999999')
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsTable [data-ads-search="user_id"]').first.click()
    expect(first).to_have_text('1000',use_inner_text=True)
    assert requests[-1]['user_id']==['2030'] and requests[-1]['offset']==['0']
    expect(page.locator('#adsFilters [name=user_id]')).to_have_value('2030')
    with page.expect_request(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsTable [data-ads-search="parent_id"]').first.click()
    expect(page.locator('#adsFilters [name=parent_id]')).to_have_value('0')
    assert requests[-1]['parent_id']==['0'] and requests[-1]['user_id']==['2030']
    assert requests[-1]['sort']==['estimate_income']
    page.fill('#adsFilters [name=user_id]','999999')
    page.locator('#adsFilters [type=submit]').click()
    page.locator('.ads-empty').wait_for()
    assert requests[-1]['offset']==['0']
    expect(page.locator('#adsPagination')).to_be_hidden()
    page.locator('#adsFilters [type=reset]').click()
    expect(first).to_have_text('1000',use_inner_text=True)
    page.locator('[data-ads-page="3"]').first.click()
    expect(first).to_have_text('1030',use_inner_text=True)
    total=2
    page.evaluate('loadAdsData()')
    expect(first).to_have_text('1000',use_inner_text=True)
    assert requests[-1]['offset']==['0']
    expect(page.locator('#adsPagination nav')).to_be_hidden()
    assert page.locator('#adsTable tbody tr').count()==2
    page.reload()
    expect(page.locator('#adsPageSizeMenu summary')).to_have_text('15')
    assert requests[-1]['limit']==['15']
    browser.close()
print('PASS: 35 records, last page, size persistence, jump, empty filter/reset and shrinking total')
