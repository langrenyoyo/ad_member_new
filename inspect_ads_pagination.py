"""Capture reference pagination against generated records, with writes blocked."""
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/ads-pagination');out.mkdir(parents=True,exist_ok=True)
seed=json.loads(Path('visual-baseline/fixtures/ads/data.json').read_text(encoding='utf-8'))
total=205
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1690,'height':1030})
    def handle(route):
        req=route.request
        if '/ad/index?' in req.url:
            q=parse_qs(urlparse(req.url).query);offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
            return route.fulfill(json={'total':total,'rows':[{**seed['reference'][0],'id':9200+i} for i in range(offset,min(total,offset+limit))],'extend':{'money1':0,'money2':0,'tixian1':0,'tixian2':0}})
        if req.method not in ('GET','HEAD') and '/index/login' not in req.url:return route.abort()
        route.continue_()
    page.route('**/*',handle)
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base+'/index/login');page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="ad?ref=addtabs"]').first.wait_for(state='attached')
    page.goto(base+'/ad',wait_until='networkidle')
    page.locator('button[name=commonSearch]').click()
    results=[]
    for number in [1,2,4,5,10,19,20,21]:
        with page.expect_response('**/ad/index?*'):
            page.evaluate('n=>jQuery("#table").bootstrapTable("selectPage",n)',number)
        page.wait_for_load_state('networkidle');page.mouse.move(0,0)
        panel=page.locator('.fixed-table-pagination')
        results.append({'page':number,**panel.evaluate("e=>({html:e.outerHTML,text:e.innerText,rect:e.getBoundingClientRect().toJSON(),styles:[e,...e.querySelectorAll('div,span,button,li,a')].filter(n=>n.getClientRects().length).map(n=>{const c=getComputedStyle(n);return {tag:n.tagName,cls:n.className,text:n.innerText,rect:n.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,margin:c.margin,color:c.color,border:c.border,background:c.backgroundColor}})})")})
        panel.screenshot(path=str(out/f'reference-{number}.png'))
    page.locator('.page-list button').click()
    page.screenshot(path=str(out/'size-reference.png'))
    results.append({'menu':page.locator('.page-list').inner_text()})
    page.locator('.page-list button').click()
    boundaries=[]
    for action in ['.page-next a','.page-pre a']:
        with page.expect_request('**/ad/index?*') as event:
            page.locator(action).click()
        boundaries.append({'action':action,'query':parse_qs(urlparse(event.value.url).query)})
        page.wait_for_load_state('networkidle')
    results.append({'boundaries':boundaries})
    page.locator('.page-list button').click()
    with page.expect_request('**/ad/index?*') as event:
        page.locator('.page-list .dropdown-menu a').get_by_text('All',exact=True).click()
    page.wait_for_load_state('networkidle')
    results.append({'all':{'query':parse_qs(urlparse(event.value.url).query),'text':page.locator('.fixed-table-pagination').inner_text(),'pageSize':page.evaluate("jQuery('#table').bootstrapTable('getOptions').pageSize")}})
    (out/'reference.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print('Reference pagination captured: first, middle, last and page sizes.')
