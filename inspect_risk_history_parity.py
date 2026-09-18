"""Read-only reference inspection with synthetic risk events and downloads."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/fixtures/risk-history');OUT.mkdir(parents=True,exist_ok=True)
source=ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))
credentials={}
for node in ast.walk(source):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
rows=[{'id':9100+i,'user_id':8100+i,'game_id':6100+i,'agent_id':7100+i,
       'user':{'username':['fixture 001','fixture <>&','fixture 003'][i],'parent_id':8000},
       'game':{'name':'fixture game '+str(i)},'agent':{'name':'fixture agent '+str(i)},
       'tagcode':['fixture-code','fixture <>&',''][i],'tags':['fixture tag','fixture <>&',''][i],
       'hardware_main_id':'fixture-device-'+str(i),'ip':'192.0.2.'+str(i+1),'network_status':i%2,
       'action':'fixture action','risk_score':10+i,'risk_level':'low','create_time':1789689600+i*60} for i in range(3)]
(OUT/'fixture-rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1690,'height':1030})
    errors=[];requests=[];mode={'many':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/index/login')
    for selector,value in credentials.items():page.fill(selector,value)
    page.locator('button[type=submit],input[type=submit]').first.click();page.wait_for_url(lambda url:'/index/login' not in url)
    def readonly(route):
        request=route.request;url=urlparse(request.url);q=parse_qs(url.query)
        if request.method not in ('GET','HEAD') or any(part in url.path for part in ('/lahei','/multi','/del','/agree','/refuse','/alipay','/ban','/coinclear')):
            route.abort();return
        if '/risk/risk' in url.path and ('sort' in q or request.headers.get('x-requested-with')=='XMLHttpRequest'):
            requests.append(q);items=[{**rows[i%3],'id':9100+i} for i in range(225)] if mode['many'] else rows
            offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',[str(len(items))])[0])
            route.fulfill(json={'total':len(items),'rows':items[offset:offset+limit]});return
        route.continue_()
    page.route('**/*',readonly)
    page.goto(BASE+'/risk/risk',wait_until='networkidle')
    page.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')&&jQuery.active===0")
    page.evaluate('document.fonts.ready')
    response=page.request.get('https://ad.leadink.cn/assets/js/backend/risk/risk.js')
    if response.ok:(OUT/'reference-controller.js').write_text(response.text(),encoding='utf-8')
    report=page.evaluate("""()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {
      table:{sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,exportDataType:o.exportDataType,maintainSelected:o.maintainSelected,ignoreColumn:o.exportOptions.ignoreColumn,
       columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,searchList:c.searchList,formatter:c.formatter?.toString()})))},
      filtersVisible:jQuery('.form-commonsearch').is(':visible'),permissions:document.querySelector('#table').dataset,toolbar:document.querySelector('#toolbar').innerHTML,
      filters:[...document.querySelectorAll('.form-commonsearch input:not([type=hidden]),.form-commonsearch select')].map(n=>({name:n.name,value:n.value})),
      cells:[...document.querySelectorAll('#table tbody tr:first-child td')].map(n=>({text:n.textContent,html:n.innerHTML})),
      geometry:[...document.querySelectorAll('#table th')].map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width}))
    }}""")
    page.locator('.panel').first.screenshot(path=str(OUT/'reference.png'))
    page.locator('[name=commonSearch]').click();page.locator('.panel').first.screenshot(path=str(OUT/'collapsed-reference.png'))
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.export button').click()
        with page.expect_download() as download:page.locator('.export [data-type="'+kind+'"]').click()
        download.value.save_as(str(OUT/('export-reference.'+kind)))
    page.wait_for_function('jQuery.active===0')
    page.locator('[name=commonSearch]').click()
    page.locator('[name=toggle]').click();page.locator('.panel').first.screenshot(path=str(OUT/'cards-reference.png'))
    report['card_geometry']=page.locator('#table tbody tr:first-child .card-view').evaluate_all("nodes=>nodes.map(n=>({html:n.innerHTML,height:n.getBoundingClientRect().height}))")
    page.locator('[name=toggle]').click()
    mode['many']=True;page.locator('.btn-refresh').click();page.wait_for_function('jQuery.active===0')
    page.locator('.fixed-table-pagination').screenshot(path=str(OUT/'pagination-reference.png'))
    mode['many']=False
    page.locator('.btn-refresh').click();page.wait_for_function('jQuery.active===0')
    page.evaluate("jQuery('#table').bootstrapTable('showColumn','user.parent_id');jQuery('#table').bootstrapTable('showColumn','agent.name')")
    report['searches']={}
    for field in ['user_id','user.username','user.parent_id','game.name','agent.name','hardware_main_id','ip']:
        with page.expect_response(lambda response:'/risk/risk' in response.url and 'limit=' in response.url):
            page.locator('#table tbody .searchit[data-field="'+field+'"]').first.click()
        page.wait_for_function('jQuery.active===0');report['searches'][field]=requests[-1]
        with page.expect_response(lambda response:'/risk/risk' in response.url and 'limit=' in response.url):
            page.locator('.form-commonsearch [type=reset]').click()
        page.wait_for_function('jQuery.active===0')
    report['date_sort']=[]
    for _ in range(2):
        with page.expect_response(lambda response:'/risk/risk' in response.url and 'limit=' in response.url):page.locator('#table th[data-field=create_time]').click()
        page.wait_for_function('jQuery.active===0');report['date_sort'].append(requests[-1])
    report['requests']=requests
    (OUT/'reference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not errors,errors
    print(json.dumps({'columns':[(c['field'],c.get('visible')) for c in report['table']['columns'][0]],'filtersVisible':report['filtersVisible'],'ignoreColumn':report['table']['ignoreColumn']}))
    browser.close()
