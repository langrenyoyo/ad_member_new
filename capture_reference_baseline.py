"""Capture route-matched first-viewport reference screenshots with persisted login state."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php/'
ROUTES=['dash','gameuser','agent','game','ad','tixian','butie','profit/coinlog','risk/userw','risk/risk','risk/userd','general/profile','book']
OUT=Path('visual-baseline/reference-captured'); OUT.mkdir(parents=True,exist_ok=True)
STATE=OUT/'storage-state.json'; manifest=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=p.chromium.launch_persistent_context('',headless=True,viewport={'width':1920,'height':1080})
    page=context.pages[0] if context.pages else context.new_page()
    page.goto(BASE+'index/login',wait_until='domcontentloaded',timeout=30000)
    page.fill('[name=username]','18532306918'); page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click(); page.wait_for_timeout(2000)
    context.storage_state(path=str(STATE))
    for route in ROUTES:
        url=BASE+route+'?ref=baseline'; item={'route':route,'url':url}
        try:
            response=page.goto(url,wait_until='domcontentloaded',timeout=30000); page.wait_for_timeout(1200)
            item.update(status=response.status if response else None,title=page.title(),final_url=page.url)
            name=route.replace('/','-'); page.screenshot(path=str(OUT/(name+'.png')),full_page=False); item['screenshot']=name+'.png'; item['viewport']=[1920,1080]; item['frames']=len(page.frames)
        except Exception as e: item['error']=str(e).splitlines()[0]
        manifest.append(item); print(route,item.get('status'),flush=True)
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    context.close(); browser.close()
