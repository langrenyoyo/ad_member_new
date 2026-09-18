"""Read-only reference/local behavior screenshots with the same synthetic rows."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--scope',choices=['single','multiple'],default='single')
parser.add_argument('--filters',action='store_true')
options=parser.parse_args()
out=Path('visual-baseline/fixtures/member-behavior'+('-multiple' if options.scope=='multiple' else '')+('-filters' if options.filters else ''));out.mkdir(parents=True,exist_ok=True)
base='https://ad.leadink.cn/DmvTqXBpfF.php'
rows=[dict(id=9001+i,user_id=42,username='fixture',game_id=237,game_name='fixture game',
           lottery_price=12+i,ecpm=3.5,adn_name='fixture',ip='192.0.2.1',network_status=i%2,tag='fixture',tags='fixture',
           is_white=i%2,status=i%2,created_at='2026-09-17T04:00:00Z',create_time=1789617600,
           ad_network_rit_id='rit',request_id='request',trans_id='trans',
           coin_before=100,coin=i+1,coin_after=101+i,type=[10,30,40][i],remark='fixture remark') for i in range(3)]
refrows=[dict(row,user={'username':row['username'],'is_white':row['is_white']},game={'name':row['game_name']}) for row in rows]
usage_rows=[dict(id=i,app_name='fixture app',count=2,package_name='test.fixture',duration_seconds=75,
                 first_used_at='2026-09-17T04:00:00Z',last_used_at='2026-09-17T05:00:00Z') for i in range(3)]
with sync_playwright() as p:
    browser=p.chromium.launch()
    ref=browser.new_page(viewport={'width':1536,'height':822})
    ref.goto(base+'/index/login')
    ref.fill('[name=username]','18532306918');ref.fill('[name=password]','123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.wait_for_url(lambda url:'/index/login' not in url)
    response=ref.request.get(base+'/gameuser/index',params={'limit':1,'offset':0,'filter':'{}','op':'{}'},headers={'X-Requested-With':'XMLHttpRequest'})
    uid=response.json()['rows'][0]['id']
    def readonly(route):
        if route.request.method not in ('GET','HEAD') or any(action in route.request.url for action in ('imeiidban','deviceidban','/del/','/multi/')):route.abort()
        elif route.request.resource_type in ('xhr','fetch'):route.fulfill(json={'total':3,'rows':refrows,'extend':{'coin':6}})
        else:route.continue_()
    ref.route('**/*',readonly)
    ref.goto(base+f'/users/{"duoge" if options.scope=="multiple" else "yige"}/index/user_id/{uid}',wait_until='networkidle')
    local=browser.new_page(viewport={'width':1920,'height':1080})
    def fixture(route):
        if route.request.url.endswith('/auth/login'):
            route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert route.request.method=='GET'
        if '/app-usage?' in route.request.url:
            route.fulfill(json={'total':len(usage_rows),'items':usage_rows});return
        summary={'coin_user':0,'coin':0,'freeze_coin':0}
        if '/lottery-records?' in route.request.url:
            summary.update(today_lottery_coin=0,today_average_coin=0,total_clicks=0,today_clicks=0,today_failed=0,
                device={'device_id':'fixture','imei':'fixture-imei','device_id_ban':0,'imei_id_ban':0,'risk_flag':0})
        route.fulfill(json={'total':3,'items':rows,'summary':{'change':6},'member_summary':summary})
    local.route('**/api/**',fixture)
    local.goto('http://127.0.0.1:3000/#members')
    local.fill('#loginForm [name=username]','fixture');local.fill('#loginForm [name=password]','fixture')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.locator('.member-filters').wait_for()
    local.evaluate("scope=>openMemberBehavior(42,237,scope)",options.scope)
    evidence={}
    for key,pane,table_id in [('lottery','first','table1'),('risk','second','table2'),('coins','four','table4')]:
        ref.locator(f'.nav-tabs a[href="#{pane}"]').click()
        ref.wait_for_function("id=>!!jQuery('#'+id).data('bootstrap.table')",arg=table_id)
        ref.wait_for_function('jQuery.active===0')
        ref.evaluate('([id,rows])=>jQuery("#"+id).bootstrapTable("load",{total:rows.length,rows,extend:{coin:6}})',[table_id,refrows])
        ref.locator(f'#{pane}').wait_for(state='visible')
        local.locator(f'[data-behavior-tab={key}]').click()
        local.locator(f'#behavior-pane-{key} tbody tr').first.wait_for()
        if options.filters:
            ref.locator(f'#{pane} button[name=commonSearch]').click()
            local.locator(f'#behavior-pane-{key} [data-action=search]').click()
            ref.locator(f'#{pane} form.form-commonsearch [name=user_id]').evaluate_all('els=>els.forEach(el=>{el.value="42";el.defaultValue="42";})')
        ref.evaluate('document.fonts.ready');local.evaluate('document.fonts.ready')
        ref.screenshot(path=str(out/f'{key}-reference.png'),animations='disabled')
        local.locator('.member-behavior-dialog main').screenshot(path=str(out/f'{key}-local.png'),animations='disabled')
        evidence[key]={}
        if options.filters:
            evidence[key]['filters']={
                'referenceLayout':ref.locator(f'#{pane} form.form-commonsearch').evaluate('''el=>[el,...el.querySelectorAll('.row,.form-group,label,input:not([type=hidden]),select,button')].map(n=>{const s=getComputedStyle(n);return {tag:n.tagName,cls:n.className,rect:n.getBoundingClientRect().toJSON(),padding:s.padding,margin:s.margin,width:s.width,display:s.display,font:s.font};})'''),
                'reference':ref.locator(f'#{pane} form.form-commonsearch input:not([type=hidden]),#{pane} form.form-commonsearch select').evaluate_all('els=>els.map(el=>({name:el.name,rect:el.getBoundingClientRect().toJSON()}))'),
                'local':local.locator(f'#behavior-pane-{key} .ads-filters [name]').evaluate_all('els=>els.map(el=>({name:el.name,rect:el.getBoundingClientRect().toJSON()}))')}
        for name,page,selector in [('reference',ref,'#'+table_id),('local',local,f'#behavior-pane-{key} table')]:
            evidence[key][name]=page.locator(selector).evaluate('''el=>({width:el.getBoundingClientRect().width,
              headers:[...el.querySelectorAll('th')].map(n=>({text:n.textContent.trim(),width:n.getBoundingClientRect().width})),
              rows:[...el.querySelectorAll('tbody tr')].map(n=>n.getBoundingClientRect().height)})''')
        if key=='coins':
            evidence[key]['summary']=ref.locator('#coin_toolbar4').evaluate('el=>({html:el.parentElement.outerHTML,font:getComputedStyle(el).font})')
    ref.locator('.nav-tabs a[href="#first"]').click()
    ref.locator('#first a.btn-dialog').first.click()
    window=ref.locator('.layui-layer-iframe').last
    window.wait_for()
    ref.add_style_tag(content='.layui-layer{animation:none!important}')
    frame=window.locator('iframe').element_handle().content_frame()
    frame.wait_for_selector('table')
    frame.evaluate('''rows=>{
      const body=document.querySelector('tbody');body.replaceChildren();
      for(const row of rows){const tr=document.createElement('tr');
        for(const value of [row.app_name,row.count,row.package_name,row.duration_seconds+'秒','2026-09-17 12:00:00','2026-09-17 13:00:00']){
          const td=document.createElement('td');td.textContent=value;tr.append(td);
        }body.append(tr);
      }
    }''',usage_rows)
    local.locator('[data-behavior-tab=lottery]').click()
    local.locator('[data-app-usage]').click()
    detail=local.locator('.member-app-usage-dialog')
    detail.locator('tbody tr').first.wait_for()
    frame.evaluate('document.fonts.ready');local.evaluate('document.fonts.ready')
    window.screenshot(path=str(out/'app-reference.png'),animations='disabled')
    detail.screenshot(path=str(out/'app-local.png'),animations='disabled')
    evidence['app']={'reference':frame.locator('table').bounding_box(),'local':detail.locator('table').bounding_box(),
                     'referenceStyles':frame.evaluate('''()=>['body','th','td'].map(selector=>{const s=getComputedStyle(document.querySelector(selector));return {selector,font:s.font,color:s.color,background:s.background,lineHeight:s.lineHeight};})'''),
                     'note':'Synthetic cell text on both sides; this comparison does not establish duration semantics.'}
    browser.close()
reports={}
for key in evidence:
    a=Image.open(out/f'{key}-reference.png').convert('RGB');b=Image.open(out/f'{key}-local.png').convert('RGB')
    assert a.size==b.size
    diff=ImageChops.difference(a,b);diff.save(out/f'{key}-diff.png')
    reports[key]={'changed_pixel_ratio':sum(max(pixel)>10 for pixel in diff.get_flattened_data())/(a.width*a.height),'mean_rgb':sum(ImageStat.Stat(diff).mean)/3}
(out/'measurements.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
print(reports)
