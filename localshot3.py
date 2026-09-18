from playwright.sync_api import sync_playwright
from pathlib import Path
out=Path('visual-baseline/local'); out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(viewport={'width':1920,'height':1080}); page.goto('http://127.0.0.1:3010/'); page.fill('[name=username]','18532306918'); page.fill('[name=password]','123456'); page.locator('#loginForm').evaluate('f=>f.requestSubmit()'); page.wait_for_timeout(2500); page.screenshot(path=str(out/'dashboard.png'),full_page=True); print(page.url, page.locator('.app-shell').is_visible()); b.close()
