from playwright.sync_api import sync_playwright
from pathlib import Path
out=Path('visual-baseline/reference'); out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(viewport={'width':1920,'height':1080}); page.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='networkidle',timeout=30000); page.fill('[name=username]','18532306918'); page.fill('[name=password]','123456'); page.locator('button[type=submit],input[type=submit]').first.click(); page.wait_for_timeout(2500)
 links=page.locator('a').evaluate_all("els=>els.map(e=>({t:(e.innerText||'').trim(),h:e.href})).filter(x=>x.h.includes('leadink'))")
 print(len(links));
 for i,x in enumerate(links): print(i,x)
 for i,x in enumerate(links[:20]):
  try: page.goto(x['h'],wait_until='networkidle',timeout=15000); page.wait_for_timeout(500); name=f'page-{i}.png'; page.screenshot(path=str(out/name),full_page=True)
  except Exception as e: print('ERR',i,e)
 b.close()
