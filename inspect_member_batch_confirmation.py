"""Observe batch confirmation with all reference business writes blocked."""
import os,json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base+'/index/login');page.fill('[name=username]',os.environ['PARITY_USERNAME']);page.fill('[name=password]',os.environ['PARITY_PASSWORD'])
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="gameuser?ref=addtabs"]').wait_for(state='attached')
    blocked=[]
    def readonly(r):
        if r.request.method not in ('GET','HEAD','OPTIONS'):
            blocked.append({'method':r.request.method,'path':r.request.url.split('?')[0].split('.php')[-1]});r.abort()
        else:r.continue_()
    page.route('**/*',readonly)
    page.goto(base+'/gameuser',wait_until='networkidle')
    page.locator('#table tbody input[type=checkbox]').first.check()
    visible=page.locator('#toolbar .btn-more').is_visible()
    controls=page.locator('#toolbar .btn-more,#toolbar .btn-multi').evaluate_all('''els=>els.map(e=>({text:e.textContent.trim(),cls:e.className,
      display:getComputedStyle(e).display,visibility:getComputedStyle(e).visibility,visible:!!e.getClientRects().length,
      ancestors:[...function*(n){while(n&&n.id!=='toolbar'){yield n;n=n.parentElement}}(e.parentElement)].map(n=>({tag:n.tagName,cls:n.className,display:getComputedStyle(n).display}))}))''')
    if visible:
        page.locator('#toolbar .btn-more').click()
        page.locator('#toolbar .btn-multi').filter(has_text='禁用').click()
        page.wait_for_timeout(500)
    dialogs=page.locator('.layui-layer').evaluate_all('''els=>els.map(e=>({text:e.textContent.trim(),cls:e.className,
      rect:e.getBoundingClientRect().toJSON(),buttons:[...e.querySelectorAll('.layui-layer-btn a')].map(b=>b.textContent.trim())}))''')
    result={'more_visible_after_selection':visible,'controls':controls,'dialogs':dialogs,'blocked_writes':blocked}
    Path('visual-baseline/reference-verified/member-batch-confirmation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True));browser.close()
