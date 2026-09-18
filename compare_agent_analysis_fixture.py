"""Compare six analysis charts and member table using identical synthetic responses."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from PIL import Image,ImageChops
from playwright.sync_api import sync_playwright

OUT=Path('visual-baseline/fixtures/agent-analysis');OUT.mkdir(parents=True,exist_ok=True)
BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
rows=[dict(id=9003-i,username='fixture-'+str(i),game_id=1,game_name='Fixture game',agent_name='Fixture agent',coin_user=20+i,coin_user_month=10+i,coin_user_day=2+i,coin=10+i,freeze_coin=i,game_addiction_enable=i%2,is_white=i%2,status=1,created_at='2026-09-18T00:00:00+00:00') for i in range(3)]
charts={'echart_coin_data':[{'name':'Low','value':1},{'name':'Other','value':2}],
 'echart_success_percent_data':[{'name':'High','value':2},{'name':'Other','value':1}],
 'echart_ip_data':[{'name':'内网','value':10},{'name':'公网','value':32}],
 'echart_app_num_data':[{'name':'One','value':1},{'name':'More','value':2}],
 'echart_game_data':{'name':['Fixture A','Fixture B'],'value':[1,2]},'echart_scatter_data':[[20,.4],[35,.5],[50,.8]]}
data={'agent_id':9000,'agent_name':'Fixture agent','items':rows,'total':3,'echart_data':charts,'can_configure':True}
(OUT/'fixture.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
credentials={}
for node in ast.walk(ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
with sync_playwright() as p:
    browser=p.chromium.launch();ref=browser.new_page(viewport={'width':1690,'height':1030})
    ref.goto(BASE+'/index/login')
    for selector,value in credentials.items():ref.fill(selector,value)
    ref.locator('button[type=submit],input[type=submit]').first.click();ref.wait_for_url(lambda url:'/index/login' not in url)
    def readonly(route):
        request=route.request;path=urlparse(request.url).path
        if request.method not in ('GET','HEAD') or any(part in path for part in ('/update','/lahei','/multi','/del','/agree','/refuse','/alipay','/ban','/coinclear','/oss')):route.abort();return
        if '/agents/assay/' in path and request.headers.get('x-requested-with')=='XMLHttpRequest':
            reference_rows=[{**row,'user':{**row,'create_time':1789689600},'game':{'id':1,'name':row['game_name']},'agent':{'name':row['agent_name']}} for row in rows]
            route.fulfill(json={'total':3,'rows':reference_rows,'echart_data':charts});return
        route.continue_()
    ref.route('**/*',readonly)
    actual=ref.request.get(BASE+'/agent/index',params={'limit':1,'offset':0},headers={'X-Requested-With':'XMLHttpRequest'}).json();aid=actual['rows'][0]['id'];del actual
    ref.goto(BASE+'/agents/assay/index/agent_id/'+str(aid),wait_until='networkidle')
    ref.wait_for_function('document.querySelectorAll("canvas").length>=6')
    ref.evaluate("document.querySelector('.alert').textContent='代理商名称：Fixture agent'")
    ref.evaluate("()=>new Promise(resolve=>require(['echarts'],E=>{document.querySelectorAll('[_echarts_instance_]').forEach(n=>E.getInstanceByDom(n).setOption({animation:false}));resolve()}))")
    ref.evaluate('document.fonts.ready');ref.wait_for_timeout(250)
    ref.locator('#main').screenshot(path=str(OUT/'reference.png'))
    ref.locator('.fixed-table-toolbar').screenshot(path=str(OUT/'charts-reference.png'))
    ref.locator('#table').screenshot(path=str(OUT/'table-reference.png'))
    local=browser.new_page(viewport={'width':1920,'height':1080});local.add_init_script("sessionStorage.setItem('agent-dashboard-id','9000')")
    def fixture(route):
        path=urlparse(route.request.url).path
        if path.endswith('/login'):route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert route.request.method=='GET'
        if path.endswith('/analysis-settings'):route.fulfill(json=dict(coin=[],success=[],apps=[]));return
        route.fulfill(json=data if path.endswith('/analysis') else {'items':[],'total':0})
    local.route('**/api/**',fixture);local.goto('http://127.0.0.1:3000/#agent-analysis')
    local.fill('#loginForm [name=username]','fixture');local.fill('#loginForm [name=password]','fixture');local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.wait_for_function('document.querySelectorAll("[data-analysis-chart] canvas").length===6')
    local.evaluate("document.querySelectorAll('[data-analysis-chart]').forEach(n=>echarts.getInstanceByDom(n).setOption({animation:false}))")
    local.evaluate('document.fonts.ready');local.wait_for_timeout(250)
    local.locator('#content').screenshot(path=str(OUT/'local.png'));local.locator('.agent-analysis-charts').screenshot(path=str(OUT/'charts-local.png'));local.locator('#agentAnalysisTable table').screenshot(path=str(OUT/'table-local.png'))
    report={'geometry':{}}
    for name,page,selectors in [('reference',ref,'#main,.alert,.commonsearch-table,.fixed-table-toolbar,#table,th'),('local',local,'#content,.agent-dashboard-name,#agentAnalysisFilters,.agent-analysis-charts,#agentAnalysisTable table,th')]:
        report['geometry'][name]=page.locator(selectors).evaluate_all('nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {tag:n.tagName,id:n.id,cls:n.className,x:r.x,y:r.y,width:r.width,height:r.height}})')
        report[name+'_cells']=page.locator('table tbody tr').first.locator('td').evaluate_all('nodes=>nodes.map(n=>({html:n.innerHTML,controls:[...n.querySelectorAll("a,button,i")].map(e=>{const c=getComputedStyle(e);return {tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,font:c.font,padding:c.padding,margin:c.margin,vertical:c.verticalAlign}})}))')
    local.locator('[data-analysis-settings=coin]').click();dialog=local.locator('.agent-analysis-settings');dialog.locator('[data-bucket-add]').click()
    for key,value in [('name','Fixture range'),('minimum','0'),('maximum','10')]:dialog.locator('[name='+key+']').fill(value)
    dialog.locator('main').click(position={'x':5,'y':300});dialog.screenshot(path=str(OUT/'settings-local.png'))
    browser.close()
for prefix in ['','charts-','table-','settings-']:
    a=Image.open(OUT/(prefix+'reference.png')).convert('RGB');b=Image.open(OUT/(prefix+'local.png')).convert('RGB');size=(max(a.width,b.width),max(a.height,b.height))
    aa=Image.new('RGB',size,'white');aa.paste(a);bb=Image.new('RGB',size,'white');bb.paste(b);diff=ImageChops.difference(aa,bb);diff.save(OUT/(prefix+'diff.png'))
    report[prefix or 'page']={'reference_size':a.size,'local_size':b.size,'changed_pixels_percent':round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(size[0]*size[1])*100,4)}
(OUT/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({key:value for key,value in report.items() if key not in ['geometry','reference_cells','local_cells']}))
