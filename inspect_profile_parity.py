"""Read-only profile inspection; replace form and log data with synthetic values."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/fixtures/profile');OUT.mkdir(parents=True,exist_ok=True)
source=ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))
credentials={}
for node in ast.walk(source):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
rows=[{'id':9100+i,'admin_id':8000,'username':'fixture','title':['fixture login','fixture <>&','fixture update'][i],
       'url':['/fixture/login','/fixture/<>&','/fixture/profile'][i],'ip':'192.0.2.'+str(i+1),
       'createtime':1789689600+i*60,'content':'{}','useragent':'fixture'} for i in range(3)]
(OUT/'fixture-rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1690,'height':1030})
    errors=[];requests=[];mode={'many':False};page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/index/login')
    for selector,value in credentials.items():page.fill(selector,value)
    page.locator('button[type=submit],input[type=submit]').first.click();page.wait_for_url(lambda url:'/index/login' not in url)
    def readonly(route):
        request=route.request;url=urlparse(request.url);q=parse_qs(url.query)
        if request.method not in ('GET','HEAD') or any(part in url.path for part in ('/update','/lahei','/multi','/del','/agree','/refuse','/alipay','/ban','/coinclear')):
            route.abort();return
        if '/general/profile' in url.path and ('sort' in q or request.headers.get('x-requested-with')=='XMLHttpRequest'):
            requests.append(q);items=[{**rows[i%3],'id':9100+i} for i in range(225)] if mode['many'] else rows
            start=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',[str(len(items))])[0])
            route.fulfill(json={'total':len(items),'rows':items[start:start+limit]});return
        route.continue_()
    page.route('**/*',readonly)
    page.goto(BASE+'/general/profile',wait_until='networkidle')
    page.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')&&jQuery.active===0")
    response=page.request.get('https://ad.leadink.cn/assets/js/backend/general/profile.js')
    if response.ok:(OUT/'reference-controller.js').write_text(response.text(),encoding='utf-8')
    page.evaluate("""()=>{
      for(const n of document.querySelectorAll('input:not([type=hidden])')){
       if(n.name.includes('password'))n.value='';
       else if(n.name.includes('nickname'))n.value='Fixture Administrator';
       else if(n.name.includes('username'))n.value='fixture';
       else if(n.name.includes('mobile'))n.value='13800000000';
      }
      document.querySelectorAll('.profile-username').forEach(n=>n.textContent='Fixture Administrator');
    }""")
    page.evaluate('document.fonts.ready')
    report=page.evaluate("""()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {
      table:{sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,search:o.search,showToggle:o.showToggle,showColumns:o.showColumns,showExport:o.showExport,showRefresh:o.showRefresh,commonSearch:o.commonSearch,
       columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,formatter:c.formatter?.toString()})))},
      fields:[...document.querySelectorAll('form input:not([type=hidden])')].map(n=>({name:n.name,id:n.id,type:n.type,disabled:n.disabled,readonly:n.readOnly,placeholder:n.placeholder,rule:n.dataset.rule,maxLength:n.maxLength})),
      forms:[...document.forms].map(n=>({id:n.id,action:n.getAttribute('action'),method:n.method})),
      structure:[...document.body.children].map(n=>({tag:n.tagName,cls:n.className,id:n.id})),
      controls:[...document.querySelectorAll('button')].map(n=>({text:n.textContent,cls:n.className,type:n.type,name:n.name})),
      avatar:[...document.querySelectorAll('.profile-user-img')].map(n=>({tag:n.tagName,src:n.getAttribute('src'),parent:n.parentElement.tagName,cls:n.parentElement.className})),
      cells:[...document.querySelectorAll('#table tbody tr:first-child td')].map(n=>({text:n.textContent,html:n.innerHTML})),
      geometry:[...document.querySelectorAll('#table th')].map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width}))
    }}""")
    report['styles']=page.evaluate("""()=>Object.fromEntries(['#main','.row','.box','.box-header','.box-body','.profile-user-img','.profile-avatar-container','.profile-username','#update-form','.form-group','#update-form input','#update-form button[type=submit]','.nav-tabs','.tab-content','.fixed-table-toolbar','.fixed-table-pagination'].map(s=>{const n=document.querySelector(s);if(!n)return [s,null];const c=getComputedStyle(n),r=n.getBoundingClientRect();return [s,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,padding:c.padding,margin:c.margin,border:c.border,background:c.backgroundColor}]}))""")
    report['upload']=page.locator('#faupload-avatar').evaluate('n=>({data:n.dataset,html:n.innerHTML})')
    report['detail_styles']=page.evaluate("""()=>Object.fromEntries(['#table .input-group','#table .input-group input','#table .input-group a','#table .input-group i','.nav-tabs a','.nav-tabs','.panel','.panel-body','.box','#faupload-avatar'].map(s=>{const n=document.querySelector(s);if(!n)return [s,null];const c=getComputedStyle(n),r=n.getBoundingClientRect();return [s,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,padding:c.padding,margin:c.margin,border:c.border,background:c.background,shadow:c.boxShadow,color:c.color,opacity:c.opacity}]}))""")
    page.locator('#main').screenshot(path=str(OUT/'reference.png'))
    page.locator('.profile-avatar-container').hover();page.locator('.box').first.screenshot(path=str(OUT/'avatar-hover-reference.png'))
    page.mouse.move(1680,1020)
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.export button').click()
        with page.expect_download() as download:page.locator('.export [data-type="'+kind+'"]').click()
        download.value.save_as(str(OUT/('export-reference.'+kind)))
    page.wait_for_function('jQuery.active===0');page.locator('[name=toggle]').click()
    page.locator('#main').screenshot(path=str(OUT/'cards-reference.png'))
    page.locator('[name=toggle]').click();mode['many']=True;page.locator('.btn-refresh').click();page.wait_for_function('jQuery.active===0')
    page.locator('.fixed-table-pagination').screenshot(path=str(OUT/'pagination-reference.png'))
    count=len(requests);page.locator('#table tbody .searchit[data-field=ip]').first.click();page.wait_for_function('jQuery.active===0')
    report['ip_search_requests_added']=len(requests)-count
    report['requests']=requests
    (OUT/'reference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not errors,errors
    print(json.dumps({'fields':report['fields'],'table':{k:v for k,v in report['table'].items() if k!='columns'},'structure':report['structure'],'controls':report['controls']}))
    browser.close()
