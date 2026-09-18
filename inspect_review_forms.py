"""Read-only review permissions and form controls; never save business row values."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/reference-verified/review-forms.json')
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1690,'height':1030})
    page.goto(BASE+'/index/login')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_url(lambda url:'/index/login' not in url)
    def readonly(route):
        path=route.request.url
        if route.request.method not in ('GET','HEAD') or any(part in path for part in ('/lahei','/agree','/refuse','/alipay','/del','/multi','imeiidban','deviceidban')):
            route.abort()
        else:route.continue_()
    page.route('**/*',readonly)
    result={}
    for resource in ['tixian','butie']:
        item=result[resource]={'probes':[],'forms':{}}
        sample=None
        for filters in [{},{'create_time':'2000-01-01 00:00:00 - 2030-01-01 00:00:00'}]:
            response=page.request.get(BASE+'/'+resource+'/index',params={'limit':1,'offset':0,'sort':'id','order':'desc','filter':json.dumps(filters),'op':json.dumps({'create_time':'RANGE'} if filters else {})},headers={'X-Requested-With':'XMLHttpRequest'})
            payload=response.json();rows=payload.get('rows',[])
            item['probes'].append({'wide_date':bool(filters),'status':response.status,'total':payload.get('total'),'keys':list(payload)})
            if rows:sample=rows[0]['id'];break
        page.goto(BASE+'/'+resource,wait_until='networkidle')
        page.wait_for_function("jQuery('#table').data('bootstrap.table')")
        item['permissions']=page.locator('#table').evaluate("el=>Object.fromEntries(Object.entries(el.dataset).filter(([key])=>key.startsWith('operate')))")
        item['toolbar']=page.locator('#toolbar').evaluate("el=>[...el.querySelectorAll('a,button')].map(n=>({text:n.textContent.trim(),classes:n.className,title:n.title,href:n.getAttribute('href'),icons:[...n.querySelectorAll('i')].map(icon=>icon.className)}))")
        rows=[{'id':9000+i,'user_id':42,'status':status,'user':{'username':'fixture','vip':0},'game':{'name':'fixture'},'agent':{'name':'fixture'},'good':{'name':'fixture'}} for i,status in enumerate([0,1,4])]
        page.evaluate("rows=>jQuery('#table').bootstrapTable('load',{total:rows.length,rows})",rows)
        item['actions']=page.locator('#table tbody tr[data-index]').evaluate_all("rows=>rows.map(row=>[...row.querySelectorAll('a,button')].filter(n=>n.closest('td')?.querySelector('.btn-editone,.btn-ajax,.btn-delone')).map(n=>({title:n.title,text:n.textContent.trim(),classes:n.className})))")
        if sample is None:
            continue
        for action in (['edit','reason'] if resource=='tixian' else ['edit']):
            page.goto(BASE+f'/{resource}/{action}/ids/{sample}',wait_until='networkidle')
            item['forms'][action]=page.locator('form').evaluate_all('''forms=>forms.map(form=>({classes:form.className,controls:[...form.querySelectorAll('input,select,textarea,button')].filter(el=>el.type!=='hidden').map(el=>({tag:el.tagName,type:el.type,name:el.name,label:el.closest('.form-group')?.querySelector('label')?.textContent.trim(),required:el.required,rule:el.dataset.rule,placeholder:el.placeholder,options:el.tagName==='SELECT'?[...el.options].map(o=>({value:o.value,text:o.text})):undefined,text:el.tagName==='BUTTON'?el.textContent.trim():undefined,rows:el.rows}))}))''')
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
    browser.close()
