"""Read-only reference inspection using synthetic ledger responses."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/fixtures/coin-logs')
OUT.mkdir(parents=True,exist_ok=True)
source=ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))
credentials={}
for node in ast.walk(source):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])

rows=[{'id':9100+i,'user_id':8100+i,'agent_id':7100+i,'game_id':6100+i,
       'user':{'username':['fixture 001','fixture <>&','fixture 003'][i]},
       'game':{'name':'fixture game '+str(i)},'agent':{'name':'fixture agent '+str(i),'game_ad_status':0},
       'coin_before':[12.5,100,0][i],'coin':[-2.5,20,0][i],'coin_after':[10,120,0][i],
       'type':[30,100,80][i],'remark':['fixture exchange','fixture <>&',''][i],
       'create_time':1789689600+i*60} for i in range(3)]
(OUT/'fixture-rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1690,'height':1030})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/index/login')
    for selector,value in credentials.items():page.fill(selector,value)
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_url(lambda url:'/index/login' not in url)
    requests=[];fixture_state={'many':False}
    def readonly(route):
        request=route.request;url=urlparse(request.url);query=parse_qs(url.query)
        if request.method not in ('GET','HEAD') or any(part in url.path for part in ('/lahei','/multi','/del','/agree','/refuse','/alipay','/ban')):
            route.abort();return
        if '/profit/coinlog' in url.path and ('sort' in query or request.headers.get('x-requested-with')=='XMLHttpRequest'):
            requests.append(query)
            items=[{**rows[i%3],'id':9100+i} for i in range(225)] if fixture_state['many'] else rows
            offset=int(query.get('offset',['0'])[0]);limit=int(query.get('limit',[str(len(items))])[0])
            route.fulfill(json={'total':len(items),'rows':items[offset:offset+limit],'extend':{'coin':17.5}});return
        route.continue_()
    page.route('**/*',readonly)
    page.goto(BASE+'/profit/coinlog',wait_until='networkidle')
    response=page.request.get('https://ad.leadink.cn/assets/js/backend/profit/coinlog.js')
    if response.ok:(OUT/'reference-controller.js').write_text(response.text(),encoding='utf-8')
    page.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')&&jQuery.active===0")
    page.evaluate('document.fonts.ready')
    metrics=page.locator('#table th').evaluate_all('els=>els.map(n=>{const c=getComputedStyle(n.firstElementChild);return {field:n.dataset.field,width:n.getBoundingClientRect().width,innerFont:c.font,innerPadding:c.padding}})')
    report=page.evaluate("""()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {
      table:{sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,exportDataType:o.exportDataType,exportOptions:{ignoreColumn:o.exportOptions.ignoreColumn},
       columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,searchList:c.searchList,formatter:c.formatter?.toString()})))},
      filters:[...document.querySelectorAll('.form-commonsearch input:not([type=hidden]),.form-commonsearch select')].map(n=>({name:n.name,value:n.value,placeholder:n.placeholder})),
      toolbar:document.querySelector('#toolbar').innerHTML,
      cells:[...document.querySelectorAll('#table tbody tr:first-child td')].map(n=>({text:n.textContent,html:n.innerHTML})),
      styles:Object.fromEntries(['.panel-body','.form-commonsearch','.form-commonsearch label','.fixed-table-toolbar','#table','.fixed-table-pagination'].map(s=>{const n=document.querySelector(s),r=n.getBoundingClientRect(),c=getComputedStyle(n);return [s,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,padding:c.padding}]}))
    }}""")
    response=page.request.get('https://ad.leadink.cn/assets/js/backend/profit/coinlog.js')
    if response.ok:(OUT/'reference-controller.js').write_text(response.text(),encoding='utf-8')
    page.locator('.panel').first.screenshot(path=str(OUT/'reference.png'))
    report['label_style']=page.locator('#table .label').first.evaluate('n=>{const c=getComputedStyle(n);return {font:c.font,padding:c.padding,color:c.color,background:c.backgroundColor}}')
    report['control_styles']=page.evaluate('''()=>Object.fromEntries(['#toolbar .btn-refresh','#toolbar .btn-default','.form-commonsearch input[name=user_id]','.form-commonsearch .sp_input','.columns button[name=toggle]','#table th'].map(s=>{const n=document.querySelector(s),c=getComputedStyle(n),p=getComputedStyle(n,'::placeholder'),r=n.getBoundingClientRect();return [s,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,padding:c.padding,border:c.border,borderBottom:c.borderBottom,placeholder:p.color}]}))''')
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.export button').click()
        with page.expect_download() as download:
            page.locator('.export [data-type="'+kind+'"]').click()
        download.value.save_as(str(OUT/('export-reference.'+kind)))
    page.wait_for_function('jQuery.active===0')
    page.locator('[name=toggle]').click()
    page.locator('.panel').first.screenshot(path=str(OUT/'cards-reference.png'))
    report['card_styles']=page.locator('#table .card-view').first.evaluate('n=>({html:n.outerHTML,styles:[n,...n.children].map(el=>{const c=getComputedStyle(el);return {tag:el.tagName,class:el.className,font:c.font,width:c.width,padding:c.padding,display:c.display,verticalAlign:c.verticalAlign}})})')
    page.locator('[name=toggle]').click()
    fixture_state['many']=True
    with page.expect_response(lambda response:'/profit/coinlog' in response.url and 'limit=' in response.url):page.locator('.btn-refresh').click()
    page.wait_for_function('jQuery.active===0')
    page.locator('.fixed-table-pagination').screenshot(path=str(OUT/'pagination-reference.png'))
    fixture_state['many']=False
    with page.expect_response(lambda response:'/profit/coinlog' in response.url and 'limit=' in response.url):
        page.locator('.form-commonsearch [type=reset]').click()
    page.wait_for_function('jQuery.active===0')
    report['reset']=page.locator('.form-commonsearch input:not([type=hidden]),.form-commonsearch select').evaluate_all('els=>els.map(n=>({name:n.name,value:n.value}))')
    report['searches']={}
    for field in ['user_id','user.username','game.name','agent.name']:
        with page.expect_response(lambda response:'/profit/coinlog' in response.url and 'limit=' in response.url):
            page.locator('#table tbody .searchit[data-field="'+field+'"]').first.click()
        page.wait_for_function('jQuery.active===0')
        report['searches'][field]=requests[-1]
        with page.expect_response(lambda response:'/profit/coinlog' in response.url and 'limit=' in response.url):
            page.locator('.form-commonsearch [type=reset]').click()
        page.wait_for_function('jQuery.active===0')
    report['requests']=requests
    report['column_metrics']=metrics
    (OUT/'reference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not errors,errors
    print('Reference ledger: synthetic table/card/pagination screenshots, six downloads and search queries captured')
    browser.close()
