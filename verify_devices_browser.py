from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1920,'height':1080});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:3010/#risk-devices');page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456');page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()');page.locator('#deviceTable table').wait_for();assert page.locator('#deviceTable th').count()==7;assert not errors;page.screenshot(path='visual-baseline/verified/risk-devices.png',full_page=True);b.close();print('Device risk browser checks passed')
