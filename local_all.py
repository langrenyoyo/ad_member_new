from playwright.sync_api import sync_playwright
from pathlib import Path
out=Path('visual-baseline/local'); out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); pg=b.new_page(viewport={'width':1920,'height':1080}); pg.goto('http://127.0.0.1:3000/'); pg.fill('[name=username]','18532306918'); pg.fill('[name=password]','123456'); pg.locator('#loginForm').evaluate('f=>f.requestSubmit()'); pg.wait_for_timeout(1200)
 hs=pg.locator('a[href^="#"]').evaluate_all("es=>[...new Set(es.map(e=>e.getAttribute('href')).filter(Boolean))]")
 for i,h in enumerate(hs):
  pg.evaluate("h=>{location.hash=h;window.dispatchEvent(new HashChangeEvent('hashchange'))}", h); pg.wait_for_timeout(500)
  if h == '#ads':
   try:
    pg.fill('input[name=watched_range]','2099-01-01 00:00:00 - 2099-01-01 23:59:59'); pg.locator('#adsFilters').evaluate('(f)=>f.requestSubmit()'); pg.wait_for_timeout(300)
   except Exception: pass
  # Keep a fixed 1920x1080 viewport and remove the 230px sidebar for stable comparisons.
  pg.screenshot(path=str(out/f'{h[1:]}.png'),full_page=False,clip={'x':230,'y':0,'width':1690,'height':1080})
 print('captured',len(hs),hs)
 b.close()
