from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    for kind in ['withdrawals','subsidies']:
        page.goto('http://127.0.0.1:3010/#'+kind,wait_until='networkidle')
        page.locator(f'#reviewFilters[data-review-kind="{kind}"]').wait_for()
        expected=page.evaluate('reviewDefaultFilters().created_range')
        assert page.locator('#reviewFilters [name=created_range]').input_value()==expected
        page.fill('#reviewFilters [name=created_range]','')
        page.fill('#reviewFilters [name=username]','nonexistent-review-filter-account')
        with page.expect_response(lambda r:'/api/v1/'+kind+'?' in r.url and 'username=nonexistent-review-filter-account' in r.url) as response:
            page.locator('#reviewFilters [type=submit]').click()
        assert response.value.status==200
        assert response.value.json()['total']==0
        page.wait_for_function("document.querySelector('.ads-table tbody')?.textContent.includes('没有找到匹配的记录')")
        assert page.locator('#reviewFilters [name=username]').input_value()=='nonexistent-review-filter-account'
        with page.expect_response(lambda r:'/api/v1/'+kind+'?' in r.url) as response:
            page.locator('#reviewFilters [type=reset]').click()
        assert response.value.status==200
        page.wait_for_function("document.querySelector('#reviewFilters [name=username]')?.value===''")
        assert page.locator('#reviewFilters [name=created_range]').input_value()==expected
        with page.expect_response(lambda r:'/api/v1/'+kind+'?' in r.url) as response:
            page.locator('[data-review-status="4"]').click()
        assert response.value.status==200
        assert all(row['status']==2 for row in response.value.json()['items'])
        page.screenshot(path=f'visual-baseline/verified/{kind}-filters.png',full_page=True)
        print(kind,'query/reset/status passed')
    assert not errors,errors
    browser.close()
