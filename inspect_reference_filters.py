import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    route=sys.argv[1] if len(sys.argv)>1 else 'ad'
    name=sys.argv[2] if len(sys.argv)>2 else 'ads'
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='domcontentloaded')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    link=page.locator(f'a[href="/DmvTqXBpfF.php/{route}?ref=addtabs"]')
    link.wait_for(state='attached')
    link.evaluate('(a)=>a.click()')
    frame=page.frame_locator(f'iframe[src*=".php/{route}"]').first
    frame.locator('input[name],select[name]').first.wait_for(state='attached')
    controls=frame.locator('select,input').evaluate_all('(els)=>els.map(e=>({tag:e.tagName,name:e.name,placeholder:e.placeholder,value:e.value,options:e.tagName==="SELECT"?Array.from(e.options).map(o=>({value:o.value,text:o.text})):undefined})).filter(e=>e.name)')
    Path(f'visual-baseline/reference-verified/{name}-controls.json').write_text(json.dumps(controls,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(controls,ensure_ascii=True))
    browser.close()
