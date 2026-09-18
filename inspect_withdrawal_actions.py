"""Read-only reference withdrawal action structure; no action submissions."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1690,'height':1030})
    base='https://ad.leadink.cn/DmvTqXBpfF.php';page.goto(base+'/index/login')
    page.fill('[name=username]',os.environ.get('PARITY_USERNAME','18532306918'));page.fill('[name=password]',os.environ.get('PARITY_PASSWORD','123456'))
    page.locator('button[type=submit],input[type=submit]').first.click();page.locator('a[href*="tixian?ref=addtabs"]').wait_for(state='attached')
    blocked=[]
    def route(r):
        if r.request.method in ('GET','HEAD','OPTIONS'):r.continue_()
        else:blocked.append({'method':r.request.method,'url':r.request.url});r.abort()
    page.route('**/*',route);page.goto(base+'/tixian',wait_until='networkidle')
    page.locator('#table tbody tr').first.wait_for()
    actions=page.locator('#table tbody tr').first.locator('td').evaluate_all('''cells=>cells.map((c,i)=>({index:i,text:c.textContent.trim(),links:[...c.querySelectorAll('a,button')].map(e=>({tag:e.tagName,text:e.textContent.trim(),href:e.href,title:e.title,classes:e.className,confirm:e.dataset.confirm}))}))''')
    Path('visual-baseline/reference-verified/withdrawal-actions.json').write_text(json.dumps({'actions':actions,'blocked_writes':blocked},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'actions':actions,'blocked_writes':blocked},ensure_ascii=True));browser.close()
