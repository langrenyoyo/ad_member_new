"""Read-only analysis inspection. Credentials are loaded without printing them."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
OUT=Path('visual-baseline/fixtures/agent-analysis');OUT.mkdir(parents=True,exist_ok=True)

def main():
    credentials={}
    for node in ast.walk(ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
            key=ast.literal_eval(node.args[0])
            if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1690,'height':1030});page=context.new_page()
        page.goto(BASE+'/index/login')
        for selector,value in credentials.items():page.fill(selector,value)
        page.locator('button[type=submit],input[type=submit]').first.click();page.wait_for_url(lambda url:'/index/login' not in url)
        requests=[]
        def readonly(route):
            request=route.request;url=urlparse(request.url)
            if request.method not in ('GET','HEAD') or any(part in url.path for part in ('/update','/lahei','/multi','/del','/agree','/refuse','/alipay','/ban','/coinclear','/oss')):
                route.abort();return
            if request.resource_type in ('xhr','fetch'):requests.append({'url':request.url,'method':request.method})
            route.continue_()
        page.route('**/*',readonly)
        actual=page.request.get(BASE+'/agent/index',params={'limit':1,'offset':0},headers={'X-Requested-With':'XMLHttpRequest'}).json()
        aid=actual['rows'][0]['id'];del actual
        page.goto(BASE+'/agents/assay/index/agent_id/'+str(aid),wait_until='networkidle')
        actual=page.request.get(BASE+'/agents/assay/index/agent_id/'+str(aid),params={'limit':10,'offset':0,'sort':'user.id','order':'desc','filter':'{}','op':'{}'},headers={'X-Requested-With':'XMLHttpRequest'}).json()
        shape={'keys':list(actual),'total':actual.get('total'),'rows':[{key:list(value) if isinstance(value,dict) else value if key in ('lottery_count','lottery_price','status','network_status','is_white','create_time') else '[omitted]' for key,value in row.items()} for row in actual.get('rows',[])[:2]],'echart_data':actual.get('echart_data')}
        if actual.get('rows'):
            row=actual['rows'][0];uid=row['user']['id'];gid=row['game']['id']
            lottery=page.request.get(BASE+'/games/lottery/index/game_id/'+str(gid),params={'limit':200,'offset':0,'filter':json.dumps({'user_id':uid}),'op':json.dumps({'user_id':'='})},headers={'X-Requested-With':'XMLHttpRequest'}).json()
            records=lottery.get('rows',[])
            shape['lottery_comparison']={'row_id_is_user':row['id']==uid,'total':lottery.get('total'),'loaded':len(records),'sum':round(sum(float(r.get('lottery_price') or 0) for r in records),4),'success_count':sum(int(r.get('status',-1))==1 for r in records),'member_coin_user':row['user']['coin_user']}
        if isinstance(shape['echart_data'],dict) and 'echart_game_data' in shape['echart_data']:
            shape['echart_data']['echart_game_data']['name']=['Fixture game '+str(i) for i in range(len(shape['echart_data']['echart_game_data'].get('name',[])))]
        del actual
        response=page.request.get('https://ad.leadink.cn/assets/js/backend/agents/assay.js')
        if response.ok:(OUT/'reference-controller.js').write_text(response.text(),encoding='utf-8')
        report=page.evaluate('''()=>({text:document.querySelector('#main')?.innerText,config:Object.fromEntries(Object.entries(window.Config||{}).map(([key,value])=>[key,Array.isArray(value)?{kind:'array',length:value.length,fields:value.length&&typeof value[0]==='object'?Object.keys(value[0]||{}):null}:typeof value])),
          elements:[...document.querySelectorAll('#main,#main *')].slice(0,180).map(n=>({tag:n.tagName,id:n.id,cls:n.className,name:n.name,type:n.type,href:n.getAttribute('href')})),
          controls:[...document.querySelectorAll('input,select,button')].map(n=>({tag:n.tagName,name:n.name,type:n.type,placeholder:n.placeholder,text:n.textContent,html:n.tagName==='SELECT'?n.innerHTML:null})),
          charts:[...document.querySelectorAll('[_echarts_instance_]')].map(n=>({id:n.id,width:n.clientWidth,height:n.clientHeight}))})''')
        page.evaluate('document.fonts.ready');page.locator('#main').screenshot(path=str(OUT/'initial-reference.png'))
        report['requests']=requests;report['response_shape']=shape
        report['filter_probes']=[]
        for field,value,op in [('coin_every','0.48,0.48','BETWEEN'),('coin_user_total','20.23,20.23','BETWEEN'),('success_percent','100,100','BETWEEN'),('app_num','1,1','BETWEEN'),('coin_every','9999,','BETWEEN')]:
            response=page.request.get(BASE+'/agents/assay/index/agent_id/'+str(aid),params={'limit':10,'offset':0,'sort':'user.id','order':'desc','filter':json.dumps({field:value}),'op':json.dumps({field:op})},headers={'X-Requested-With':'XMLHttpRequest'})
            try:result=response.json()
            except ValueError:result={}
            report['filter_probes'].append({'field':field,'value':value,'http_status':response.status,'is_json':bool(result),'total':result.get('total'),'scatter':result.get('echart_data',{}).get('echart_scatter_data')})
        report['links']=page.locator('#main a').evaluate_all('nodes=>nodes.map(n=>({text:n.textContent.trim(),href:n.getAttribute("href"),cls:n.className}))')
        report['layout']=page.locator('#main,.panel,.panel-body,.commonsearch-table,.row,[id^=echart],.table,.bootstrap-table,.fixed-table-toolbar').evaluate_all('nodes=>nodes.map(n=>{const r=n.getBoundingClientRect(),c=getComputedStyle(n);return {tag:n.tagName,id:n.id,cls:n.className,x:r.x,y:r.y,width:r.width,height:r.height,padding:c.padding,margin:c.margin}})')
        report['settings']={}
        page.locator('.btn-coinedit').click();page.wait_for_timeout(700)
        frame=next(f for f in page.frames if '/assay/coinedit/' in f.url)
        report['settings_window']=page.locator('.layui-layer').evaluate('n=>({width:n.offsetWidth,height:n.offsetHeight,title:n.querySelector(".layui-layer-title").textContent,buttons:n.querySelector(".layui-layer-setwin").innerHTML,shade:!!document.querySelector(".layui-layer-shade")})')
        frame.get_by_text('追加',exact=False).first.click()
        fields=frame.locator('form input[type=text]')
        for index,value in enumerate(['Fixture range','0','10']):fields.nth(index).fill(value)
        frame.locator('body').click(position={'x':5,'y':300})
        page.locator('.layui-layer').screenshot(path=str(OUT/'settings-reference.png'))
        report['settings_layout']=frame.locator('form,dl,dt,dd,table,th,td,input,button,a').evaluate_all('nodes=>nodes.filter(n=>n.offsetWidth).map(n=>{const r=n.getBoundingClientRect(),c=getComputedStyle(n);return {tag:n.tagName,cls:n.className,text:n.tagName==="INPUT"?null:n.children.length?null:n.textContent.trim(),name:n.name,x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,padding:c.padding,margin:c.margin}})')
        for key in ['coinedit','successpercentedit','appnumedit']:
            settings=context.new_page();settings.route('**/*',readonly)
            settings.goto(BASE+'/assay/'+key+'/agent_id/'+str(aid),wait_until='networkidle')
            report['settings'][key]={'text':settings.locator('body').inner_text(),'fields':settings.locator('form input').evaluate_all('nodes=>nodes.filter(n=>n.type!=="hidden").map(n=>({name:n.name,type:n.type,value:n.value}))')}
            settings.get_by_text('追加',exact=False).first.click()
            report['settings'][key]['added_fields']=settings.locator('form input,form textarea').evaluate_all('nodes=>nodes.filter(n=>n.type!=="hidden").map(n=>({name:n.name,type:n.type,value:n.value}))')
            settings.close()
        (OUT/'reference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'probes':report['filter_probes'],'settings_window':report['settings_window']},ensure_ascii=True))
        browser.close()

if __name__=='__main__':main()
