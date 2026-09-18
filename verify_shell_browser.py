from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.locator('#nav a[href="#games"]').click()
    page.locator('.target-tabs a[href="#games"][aria-current=page]').wait_for()
    page.locator('.target-tabs a[href="#members"]').click()
    page.locator('.member-filters').wait_for()
    toggle=page.locator('.shell-sidebar-toggle')
    toggle.click()
    assert toggle.get_attribute('aria-expanded')=='false'
    assert page.locator('.sidebar').bounding_box()['width']==50
    toggle.click()
    assert page.locator('.sidebar').bounding_box()['width']==230
    page.reload(wait_until='networkidle')
    page.locator('.member-filters').wait_for()
    assert page.locator('#accountName').inner_text()!='-'
    assert page.locator('.target-tabs a[aria-current=page]').count()==1
    assert not errors,errors
    page.screenshot(path='visual-baseline/verified/shell.png',full_page=True)
    browser.close()
    print('Shell browser checks passed: navigation, tabs, collapse, account reload')
