from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True)
 page=b.new_page()
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:3010')
 page.fill('[name=username]','18532306918')
 page.fill('[name=password]','123456')
 page.click('.login-submit')
 page.wait_for_timeout(1500)
 print('shell',page.locator('.app-shell').is_visible(),'errors',errors)
 print(page.locator('#content').inner_text()[:400])
 b.close()
