from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--disable-gpu','--no-sandbox'])
    page=browser.new_page(viewport={'width':1920,'height':1080},accept_downloads=True)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/#ads',wait_until='domcontentloaded',timeout=15000)
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.wait_for_timeout(2000); print('url',page.url,'error',page.locator('#loginError').text_content())
    assert page.locator('.ads-table th:visible').count()==20
    page.screenshot(path='visual-baseline/verified/ads.png',full_page=True)
    page.fill('#adsFilters [name=watched_range]','')
    page.locator('#adsFilters [name=is_fu]').select_option('')
    with page.expect_response(lambda response:'/api/v1/ads?' in response.url) as result:
        page.locator('#adsFilters [type=submit]').click()
    assert result.value.ok
    assert result.value.json()['total']>0
    page.locator('.ads-table td').first.wait_for()
    page.fill('#adsFilters [name=user_id]','999999999')
    with page.expect_response(lambda response:'/api/v1/ads?' in response.url) as result:
        page.locator('#adsFilters [type=submit]').click()
    assert result.value.json()['total']==0
    page.locator('.ads-empty').wait_for()
    assert page.locator('#adsFilters [name=user_id]').input_value()=='999999999'
    page.locator('#adsExportToggle').click()
    with page.expect_download() as download:
        page.locator('[data-ads-export=csv]').click()
    assert download.value.suggested_filename.startswith('export_') and download.value.suggested_filename.endswith('.csv')
    with page.expect_response(lambda response:'/api/v1/ads?' in response.url):
        page.locator('#adsFilters [type=reset]').click()
    assert page.locator('#adsFilters [name=user_id]').input_value()==''
    assert page.locator('#adsFilters [name=is_fu]').input_value()=='0'
    assert not errors,errors
    browser.close()
    print('Ads browser checks passed: filters, empty state, retention, reset, export')


