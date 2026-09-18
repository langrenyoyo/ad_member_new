"""Read reference lookup contracts without writing business records."""
import json
from pathlib import Path
from urllib.parse import parse_qs
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/fixtures/ads-lookups');out.mkdir(parents=True,exist_ok=True)
queries=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1690,'height':1030})
    def handle(route):
        req=route.request
        if '/ajax/gameList_source/' in req.url or '/ajax/agentList_source/' in req.url:
            agent='/agentList_' in req.url
            values=parse_qs(req.post_data or '')
            queries.append({'url':req.url.split('?')[0],'params':values})
            rows=[{'id':(6200 if agent else 7200)+i,'name':('对照代理商' if agent else '对照游戏')+f' {i:02d}'} for i in range(12)]
            offset=(int(values.get('pageNumber',['1'])[0])-1)*10
            return route.fulfill(json={'total':len(rows),'list':rows[offset:offset+10]})
        if '/ad/index?' in req.url:return route.fulfill(json={'total':0,'rows':[],'extend':{'money1':0,'money2':0,'tixian1':0,'tixian2':0}})
        if req.method not in ('GET','HEAD') and '/index/login' not in req.url:return route.abort()
        route.continue_()
    page.route('**/*',handle)
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base+'/index/login');page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="ad?ref=addtabs"]').first.wait_for(state='attached')
    page.goto(base+'/ad',wait_until='networkidle')
    result={}
    for kind in ['game','agent']:
        field=page.locator('[name="'+kind+'.name_text"]')
        field.click()
        page.locator('.sp_result_area:visible .sp_results li').nth(9).wait_for()
        result[kind]=field.evaluate("e=>{const p=jQuery(e).data('selectPageObject'),c=getComputedStyle(e);return {options:p.option,hidden:p.elem.hidden[0].outerHTML,rect:e.getBoundingClientRect().toJSON(),font:c.font,container:p.elem.container[0].outerHTML}}")
        page.locator('.sp_result_area:visible .sp_results li').first.click()
        result[kind]['selected']=field.evaluate("e=>({visible:e.value,hidden:jQuery(e).data('selectPageObject').elem.hidden[0].outerHTML})")
    result['query']=page.evaluate("()=>jQuery('#table').bootstrapTable('getOptions').queryParams({})")
    result['requests']=queries
    (out/'contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print('Reference ad lookup contract captured.')
