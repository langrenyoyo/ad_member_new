from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/#coin-logs')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('#coinTable table').wait_for()
    assert page.locator('#coinTable th').count()==11
    page.screenshot(path='visual-baseline/verified/coin-logs.png',full_page=True)
    page.fill('#coinFilters [name=created_range]','')
    with page.expect_response(lambda response:'/api/v1/coin-logs?' in response.url) as response:
        page.locator('#coinFilters [type=submit]').click()
    assert response.value.ok and response.value.json()['total']>0
    page.fill('#coinFilters [name=username]','not-a-member')
    with page.expect_response(lambda response:'/api/v1/coin-logs?' in response.url) as response:
        page.locator('#coinFilters [type=submit]').click()
    assert response.value.json()['total']==0
    assert response.value.json()['summary']['change']==0
    page.locator('#coinFilters [type=reset]').click()
    page.wait_for_function("document.querySelector('#coinFilters [name=username]')?.value==='' && document.querySelector('#coinFilters [name=created_range]')?.value!==''")
    assert not errors,errors
    browser.close()
    print('Coin log browser checks passed: columns, queries, empty summary, reset')
