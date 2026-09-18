"""Capture review layout and search toggle behavior without business mutations."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.goto('https://ad.leadink.cn/DmvTqXBpfF.php/index/login',wait_until='domcontentloaded')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    for route,name in [('tixian','withdrawals'),('butie','subsidies')]:
        link=page.locator(f'a[href="/DmvTqXBpfF.php/{route}?ref=addtabs"]')
        link.wait_for(state='attached');link.evaluate('(a)=>a.click()')
        frame=page.frame_locator(f'iframe[src*=".php/{route}"]').first
        frame.locator('input[name=user_id]').wait_for(state='visible')
        data=frame.locator('body').evaluate('''body=>({
          pagination:(()=>{const w=body.ownerDocument.defaultView,o=w.jQuery('#table').bootstrapTable('getOptions');return {pageSize:o.pageSize,pageList:o.pageList};})(),
          buttons:Array.from(body.querySelectorAll('.fixed-table-toolbar button')).map(e=>({title:e.title,text:e.textContent.trim(),class:e.className})),
          form:Array.from(body.querySelectorAll('.form-commonsearch .form-group')).map(e=>({text:e.querySelector('label')?.textContent.trim(),rect:e.getBoundingClientRect().toJSON(),input:e.querySelector('input:not([type=hidden]),select')?.getBoundingClientRect().toJSON()}))
        })''')
        search=frame.locator('button[name=commonSearch]')
        data['toggle_found']=search.count()==1
        if data['toggle_found']:
            search.click()
            frame.locator('input[name=user_id]').wait_for(state='hidden')
            data['collapsed']=True
            search.click()
            frame.locator('input[name=user_id]').wait_for(state='visible')
            data['restored']=True
        Path(f'visual-baseline/reference-verified/{name}-layout.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,json.dumps(data,ensure_ascii=True))
    browser.close()
