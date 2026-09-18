from playwright.sync_api import sync_playwright
from pathlib import Path
out=Path('visual-baseline/reference'); out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(viewport={'width':1920,'height':1080}); page.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='networkidle',timeout=30000); page.fill('input[name=username]','18532306918'); page.fill('input[name=password]','123456'); page.check('input[name=keeplogin]'); page.locator('button[type=submit],input[type=submit]').first.click(); page.wait_for_timeout(3000); print(page.url); print(page.locator('body').inner_text()[:500]); page.screenshot(path=str(out/'dashboard.png'),full_page=True); b.close()
