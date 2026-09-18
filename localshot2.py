from playwright.sync_api import sync_playwright
from pathlib import Path
out=Path('visual-baseline/local'); out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(viewport={'width':1920,'height':1080})
 try:
  page.goto('http://127.0.0.1:3010/DmvTqXBpfF.php/index/login',wait_until='domcontentloaded',timeout=10000)
  page.screenshot(path=str(out/'login.png'),full_page=True)
  for sel,val in [('[name=username]','18532306918'),('[name=password]','123456')]:
   if page.locator(sel).count(): page.fill(sel,val)
  btn=page.locator('button[type=submit],input[type=submit]').first
  if btn.count():
   btn.click(timeout=5000,no_wait_after=True)
   page.wait_for_timeout(2000)
  page.screenshot(path=str(out/'dashboard.png'),full_page=True)
  print('url',page.url)
 except Exception as e:
  print('ERR',e)
  page.screenshot(path=str(out/'error.png'),full_page=True)
 b.close()
