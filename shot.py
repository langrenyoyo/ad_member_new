from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(viewport={'width':1920,'height':1080}); page.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='networkidle',timeout=30000); print(page.title()); print(page.locator('input').count()); print(page.locator('input').evaluate_all("els=>els.map(e=>({name:e.name,type:e.type,placeholder:e.placeholder}))")); page.screenshot(path='login-reference.png',full_page=True); b.close()
