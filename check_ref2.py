from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);pg=b.new_page(viewport={'width':1920,'height':1080});pg.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='domcontentloaded',timeout=30000);print(pg.title(),pg.url);print(pg.locator('body').inner_text()[:300]);b.close()
