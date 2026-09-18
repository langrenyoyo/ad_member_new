"""Capture only explicit read-only admin routes; never traverse arbitrary links."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/reference-verified');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='networkidle')
    page.fill('[name=username]','18532306918')
    page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_load_state('networkidle')
    page.screenshot(path=str(out/'landing.png'),full_page=True)
    links=page.locator('a').evaluate_all('(els)=>els.map(e=>({text:e.innerText.trim(),href:e.getAttribute("href"),url:e.getAttribute("data-url")}))')
    (out/'navigation.json').write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf-8')
    routes={'dashboard':'dash','members':'gameuser','agents':'agent','games':'game','ads':'ad','withdrawals':'tixian','subsidies':'butie','coin-logs':'profit/coinlog','risk-whitelist':'risk/userw','risk-history':'risk/risk','risk-devices':'risk/userd','profile':'general/profile','book':'book'}
    manifest=[]
    for name,path in routes.items():
        url='https://ad.leadink.cn/DmvTqXBpfF.php/'+path+'?ref=addtabs'
        entry={'page':name,'reference_url':url,'local_route':'#'+name,'screenshot':name+'.png','layout':'admin shell with content iframe'}
        try:
            response=page.goto(url,wait_until='networkidle',timeout=30000)
            entry['status']=response.status
            text='\n'.join(frame.locator('body').inner_text() for frame in page.frames)
            entry['valid']=response.ok and '请登录后操作' not in text and 'name="password"' not in page.content()
            page.screenshot(path=str(out/entry['screenshot']),full_page=True)
            (out/(name+'.txt')).write_text(text,encoding='utf-8')
        except Exception as error:
            entry.update(valid=False,error=str(error).splitlines()[0])
        manifest.append(entry)
        print(name,entry['valid'],flush=True)
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
