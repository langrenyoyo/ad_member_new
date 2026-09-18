"""Read-only whitelist inspection with synthetic browser responses."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/fixtures/whitelist');OUT.mkdir(parents=True,exist_ok=True)
source=ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))
credentials={}
for node in ast.walk(source):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
rows=[{'id':8100+i,'username':['fixture 001','fixture <>&','fixture 003'][i],'image_url':'','parent_id':8000,
       'parent_username':'fixture parent','parent_name':'fixture parent','game_id':6100+i,'agent_id':7100+i,
       'game':{'name':'fixture game '+str(i)},'agent':{'name':'fixture agent '+str(i)},'name':'fixture name '+str(i),
       'coin_user':100+i,'coin_user_month':10+i,'coin_user_day':i,'coin':10.5+i,'freeze_coin':0,
       'is_white':1,'status':1-i%2,'game_addiction_enable':i%2,'game_addiction_time':'2026-09-18 08:00:00',
       'exchange_enable':1,'last_login_device_id':'fixture-device','last_login_ip':'192.0.2.1',
       'last_login_time':1789689600,'create_time':1789689600} for i in range(3)]
(OUT/'fixture-rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1690,'height':1030})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/index/login')
    for selector,value in credentials.items():page.fill(selector,value)
    page.locator('button[type=submit],input[type=submit]').first.click();page.wait_for_url(lambda url:'/index/login' not in url)
    requests=[]
    def readonly(route):
        request=route.request;url=urlparse(request.url);q=parse_qs(url.query)
        if request.method not in ('GET','HEAD') or any(part in url.path for part in ('/lahei','/multi','/del','/agree','/refuse','/alipay','/ban','/coinclear')):
            route.abort();return
        if '/risk/userw' in url.path and ('sort' in q or request.headers.get('x-requested-with')=='XMLHttpRequest'):
            requests.append(q);route.fulfill(json={'total':3,'rows':rows});return
        route.continue_()
    page.route('**/*',readonly)
    page.goto(BASE+'/risk/userw',wait_until='networkidle')
    page.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')&&jQuery.active===0")
    page.evaluate('document.fonts.ready')
    report=page.evaluate("""()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {
      table:{sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,exportDataType:o.exportDataType,maintainSelected:o.maintainSelected,
       columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,searchList:c.searchList})))},
      permissions:document.querySelector('#table').dataset,toolbar:document.querySelector('#toolbar').innerHTML,
      filters:[...document.querySelectorAll('.form-commonsearch input:not([type=hidden]),.form-commonsearch select')].map(n=>({name:n.name,value:n.value})),
      cells:[...document.querySelectorAll('#table tbody tr:first-child td')].map(n=>({text:n.textContent,html:n.innerHTML})),
      buttons:[...document.querySelectorAll('#table tbody tr:first-child a')].filter(n=>n.getClientRects().length).map(n=>({text:n.textContent,classes:n.className,title:n.title,url:n.href}))
    }}""")
    response=page.request.get('https://ad.leadink.cn/assets/js/backend/risk/userw.js')
    if response.ok:(OUT/'reference-controller.js').write_text(response.text(),encoding='utf-8')
    page.locator('.panel').first.screenshot(path=str(OUT/'reference.png'))
    report['geometry']=page.locator('#table tr').evaluate_all("nodes=>nodes.map(n=>[...n.children].map(c=>({width:c.getBoundingClientRect().width,height:c.getBoundingClientRect().height})))")
    report['control_styles']=page.locator('#table tbody tr:first-child input,#table tbody tr:first-child .btn-change,#table tbody tr:first-child .btn-change i,#table tbody tr:first-child .btn').evaluate_all("nodes=>nodes.map(n=>{const c=getComputedStyle(n),r=n.getBoundingClientRect();return {html:n.outerHTML,font:c.font,color:c.color,display:c.display,verticalAlign:c.verticalAlign,margin:c.margin,padding:c.padding,width:r.width,height:r.height}})")
    page.locator('[name=commonSearch]').click();page.locator('.form-commonsearch').wait_for(state='visible')
    page.locator('.panel').first.screenshot(path=str(OUT/'expanded-reference.png'))
    page.locator('[name=toggle]').click();page.locator('.panel').first.screenshot(path=str(OUT/'cards-reference.png'))
    report['card_geometry']=page.locator('#table tbody tr:first-child .card-view').evaluate_all("nodes=>nodes.map(n=>({html:n.innerHTML,height:n.getBoundingClientRect().height,lineHeight:getComputedStyle(n).lineHeight}))")
    page.locator('[name=toggle]').click()
    for selected in (False,True):
        if selected:page.locator('[name=btSelectItem]').first.check()
        for kind in ['json','xml','csv','txt','doc','excel']:
            page.locator('.export button').click()
            with page.expect_download() as download:page.locator('.export [data-type="'+kind+'"]').click()
            download.value.save_as(str(OUT/('export-'+('selected-' if selected else '')+'reference.'+kind)))
        page.wait_for_function('jQuery.active===0')
    page.evaluate("jQuery('#table').bootstrapTable('showColumn','last_login_ip')")
    page.locator('[name=commonSearch]').click();ip_requests_before=len(requests)
    page.locator('#table tbody .searchit[data-field=last_login_ip]').first.click();page.wait_for_function('jQuery.active===0')
    report['ip_search']={'requests_added':len(requests)-ip_requests_before,'expanded':page.locator('.form-commonsearch').is_visible(),'query':requests[-1],'filters':page.locator('.form-commonsearch input').evaluate_all('nodes=>nodes.map(n=>({name:n.name,value:n.value,type:n.type}))')}
    report['requests']=requests
    (OUT/'reference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not errors,errors
    print(json.dumps({'permissions':report['permissions'],'toolbar':report['toolbar'],'buttons':report['buttons']},ensure_ascii=True))
    browser.close()
