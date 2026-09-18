from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); pg=b.new_page(); pg.goto('http://127.0.0.1:3010/'); pg.fill('[name=username]','18532306918'); pg.fill('[name=password]','123456'); pg.locator('#loginForm').evaluate('f=>f.requestSubmit()'); pg.wait_for_timeout(1000); pg.goto('http://127.0.0.1:3010/#members'); pg.wait_for_timeout(500); print('filters',pg.locator('[data-mf]').count(),'rows',pg.locator('tbody tr').count()); b.close()
