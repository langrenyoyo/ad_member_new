from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/#book')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('.tutorial-table').wait_for()
    assert page.locator('[data-tutorial]').count()==2
    page.screenshot(path='visual-baseline/verified/book.png',full_page=True)
    page.locator('[data-tutorial="3"]').click()
    page.locator('#tutorialDialog').wait_for()
    assert page.locator('.tutorial-content img').count()==9
    try:
        page.wait_for_function("Array.from(document.querySelectorAll('.tutorial-content img')).every(img=>img.complete&&img.naturalWidth>0)",timeout=10000)
        images_loaded=True
    except Exception:
        images_loaded=False
    page.screenshot(path='visual-baseline/verified/book-detail.png')
    page.keyboard.press('Escape')
    page.locator('#tutorialDialog').wait_for(state='detached')
    page.fill('#tutorialSearch','快手')
    assert page.locator('[data-tutorial]').count()==1
    page.locator('[data-tutorial="2"]').click()
    page.locator('#tutorialDialog button').click()
    assert not errors,errors
    browser.close()
    print('Tutorial interaction checks passed: list, both details, search, close')
    assert images_loaded, 'Tutorial image completeness failed: original image host unavailable'
