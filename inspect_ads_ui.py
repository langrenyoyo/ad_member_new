"""Inspect ad controls using generated browser data and block remote writes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path('visual-baseline/fixtures/ads')
data = json.loads((out / 'data.json').read_text(encoding='utf-8'))
payload = {'total': len(data['reference']), 'rows': data['reference'], 'extend': {'money1':111.5,'money2':11.15,'tixian1':0,'tixian2':0}}
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1690,'height':1030}, timezone_id='Asia/Shanghai', accept_downloads=True)
    def route_request(route):
        request = route.request
        if '/ad/index' in request.url and request.resource_type in ('xhr','fetch'):
            return route.fulfill(json=payload)
        if request.method not in ('GET','HEAD') and '/index/login' not in request.url:
            return route.abort()
        route.continue_()
    page.route('**/*',route_request)
    base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base+'/index/login',wait_until='domcontentloaded')
    page.fill('[name=username]','18532306918')
    page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="ad?ref=addtabs"]').first.wait_for(state='attached')
    page.goto(base+'/ad',wait_until='networkidle')
    page.wait_for_function("window.jQuery && jQuery('#table').data('bootstrap.table')")
    page.evaluate("data=>jQuery('#table').bootstrapTable('load',data)",payload)
    styles = page.evaluate("""()=>{
      const sels=['body','.panel-body','.fixed-table-toolbar','.fixed-table-toolbar .columns', '.fixed-table-toolbar button','.btn-refresh','.btn-export','#toolbar a','.pagination-info','.fixed-table-pagination','.fixed-table-container','.th-inner','.label','#table td','#table a','.keep-open .dropdown-menu label','.keep-open .dropdown-menu'];
      const styles=sels.map(selector=>({selector,elements:[...document.querySelectorAll(selector)].filter(e=>e.getClientRects().length).slice(0,12).map(e=>{const c=getComputedStyle(e);return {html:e.outerHTML,rect:e.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,margin:c.margin,color:c.color,background:c.backgroundColor,border:c.border,shadow:c.boxShadow}})}));
      const o=jQuery('#table').bootstrapTable('getOptions');return {styles,options:{exportDataType:o.exportDataType,exportTypes:o.exportTypes,exportOptions:o.exportOptions,cardView:o.cardView},toolbar:document.querySelector('.fixed-table-toolbar').outerHTML};
    }""")
    (out/'controls-reference.json').write_text(json.dumps(styles,ensure_ascii=False,indent=2),encoding='utf-8')
    page.locator('button[name=commonSearch]').click()
    page.locator('.keep-open button').click()
    page.screenshot(path=str(out/'columns-reference.png'))
    page.locator('.keep-open button').click()
    page.locator('.export button').click()
    page.screenshot(path=str(out/'export-reference.png'))
    page.locator('.export button').click()
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.export button').click()
        with page.expect_download() as event:
            page.locator(f'.export [data-type="{kind}"]').click()
        event.value.save_as(out/f'export-reference.{kind}')
    page.locator('button[name=toggle]').click()
    page.screenshot(path=str(out/'card-reference.png'))
    card=page.locator('#table').evaluate("t=>({html:t.outerHTML,rect:t.getBoundingClientRect().toJSON(),cells:[...t.querySelectorAll('td,.card-view,.title,.value')].slice(0,12).map(e=>{const c=getComputedStyle(e);return {text:e.innerText,rect:e.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,margin:c.margin,display:c.display,width:c.width,minWidth:c.minWidth,verticalAlign:c.verticalAlign}})})")
    (out/'card-reference.json').write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print('Captured reference ad toolbar, column menu, six exports and card view.')
