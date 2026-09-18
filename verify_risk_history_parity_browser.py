"""Risk list interactions and request isolation; all API data is in memory."""
import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    rows=[{'id':9100+i,'user_id':8100+i,'username':'fixture '+str(i),'parent_id':8000+i,'game_id':6100+i,'game_name':'fixture game '+str(i),
           'agent_id':7100+i,'agent_name':'fixture agent '+str(i),'tagcode':'fixture-code '+str(i),'tags':'fixture <>& '+str(i),
           'hardware_main_id':'fixture-device '+str(i),'ip':'192.0.2.'+str(i+1),'action':'fixture action','risk_score':i,'risk_level':'low',
           'created_at':'2026-09-18T00:00:'+str(i%60).zfill(2)+'Z'} for i in range(225)]
    reads=[];held=[];errors=[];mode={'fail':False,'hold':False,'drift':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        request=route.request;url=urlparse(request.url);path=url.path.split('/api/')[-1].removeprefix('v1/');q=parse_qs(url.query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert request.method=='GET',request.url
        if path.startswith('member-filter-options/'):
            kind='game' if path.endswith('/games') else 'agent';base=6100 if kind=='game' else 7100
            options=[{'id':base+i,'name':'fixture '+kind+' '+str(i)} for i in range(225)]
            if 'id' in q:options=[r for r in options if str(r['id'])==q['id'][0]]
            if 'q' in q:options=[r for r in options if q['q'][0] in r['name']]
            offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
            route.fulfill(json={'items':options[offset:offset+limit],'total':len(options)});return
        if path!='risk/history':route.fulfill(json={'items':[],'total':0});return
        reads.append(q)
        if mode['hold']:held.append(route);return
        if mode['fail']:route.fulfill(status=503,json={'detail':'fixture unavailable'});return
        items=list(rows)
        for key in ['game_id','agent_id','parent_id','ip']:
            if key in q:items=[r for r in items if str(r[key])==q[key][0]]
        for key in ['user_id','username','agent_name','tagcode','hardware_main_id']:
            if key in q:items=[r for r in items if q[key][0] in str(r[key])]
        if 'game_name_exact' in q:items=[r for r in items if r['game_name']==q['game_name_exact'][0]]
        items.sort(key=lambda r:(r[q.get('sort',['id'])[0]],r['id']),reverse=q.get('order',['desc'])[0]=='desc')
        offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
        route.fulfill(json={'items':items[offset:offset+limit],'total':len(items)+(1 if mode['drift'] and offset else 0)})
    page.route('**/api/**',fixture);page.goto('http://127.0.0.1:3000/#risk-history')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    form=page.locator('#riskHistoryFilters');table=page.locator('#riskHistoryTable');error=page.locator('#riskHistoryError')
    def ready(count=10):
        page.wait_for_function('n=>document.querySelector("#riskHistoryTable tbody")?.rows.length===n&&!document.querySelector("#riskHistoryTable").hasAttribute("aria-busy")',arg=count)
        assert error.inner_text()=='',error.inner_text()
    def submit():form.evaluate('f=>f.requestSubmit()')
    def reset():form.locator('[type=reset]').click();ready()
    ready();assert form.is_visible() and table.locator('th').count()==12
    assert reads[-1]=={'limit':['10'],'offset':['0'],'sort':['id'],'order':['desc']}
    assert table.locator('[data-sort]').count()==1 and table.locator('[data-sort=created_at]').count()==1
    assert not table.locator('input, [data-member-behavior]').count()
    # Seven reference search links, including default-hidden fields.
    page.locator('.game-user-columns summary').click()
    for key in ['parent_id','agent_name']:page.locator('[data-column='+key+']').check()
    page.locator('.game-user-columns summary').click()
    for key,value in [('user_id','8324'),('username','fixture 224'),('parent_id','8224'),('hardware_main_id','fixture-device 224'),('ip','192.0.2.225')]:
        table.locator('[data-risk-search='+key+']').first.click();ready(1);assert reads[-1][key]==[value];reset()
    table.locator('[data-risk-search=game_name]').first.click();ready(1)
    assert reads[-1]['game_name_exact']==['fixture game 224'] and 'game_id' not in reads[-1]
    reset();assert 'game_name_exact' not in reads[-1]
    form.locator('[data-filter-lookup=game_id]').click();page.locator('.member-lookup-results:visible .sp_results li').first.click();submit();ready(1)
    assert reads[-1]['game_id']==['6100'] and 'game_name_exact' not in reads[-1]
    table.locator('[data-risk-search=game_name]').first.click();ready(1);assert reads[-1]['game_name_exact']==['fixture game 0'] and 'game_id' not in reads[-1]
    reset();table.locator('[data-risk-search=agent_name]').first.click();ready(1)
    assert reads[-1]['agent_name']==['fixture agent 224'] and 'agent_id' not in reads[-1]
    reset();form.locator('[name=tagcode]').fill('fixture-code 224');submit();ready(1);reset()
    page.locator('#riskHistorySearch').click();assert not form.is_visible()
    table.locator('[data-risk-search=ip]').first.click();ready(1);assert form.is_visible();reset()
    form.locator('[name=created_range]').fill('2026-02-30 00:00:00 - 2026-03-01 00:00:00');count=len(reads);submit()
    page.wait_for_function('document.querySelector("#riskHistoryError").textContent!==""');assert len(reads)==count
    reset();form.locator('[name=created_range]').click();page.locator('.daterangepicker:visible').wait_for();form.locator('[name=username]').click()
    # Pagination, cyclic ends, jump and date sort.
    page.locator('#riskHistoryPagination [aria-label="上一页"]').click();ready(5);assert reads[-1]['offset']==['220']
    page.locator('#riskHistoryPagination [aria-label="下一页"]').click();ready();assert reads[-1]['offset']==['0']
    page.locator('#riskHistoryPagination input').fill('5');page.locator('[data-game-jump]').click();ready();assert reads[-1]['offset']==['40']
    for order in ['desc','asc']:
        table.locator('[data-sort=created_at]').click();ready();assert reads[-1]['order']==[order] and reads[-1]['offset']==['0']
        assert table.locator('[data-sort=created_at]').evaluate('async el=>{const i=new Image();i.src=getComputedStyle(el).backgroundImage.slice(5,-2);await i.decode();return i.naturalWidth===19;}')
    page.locator('#riskHistoryPagination .game-page-size summary').click();page.locator('[data-game-size=All]').click();ready(225)
    assert reads[-2]['limit']==['200'] and reads[-1]['offset']==['200']
    # Six full downloads, no checkbox selection and first visible column excluded as reference.
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        content=Path(download.value.path()).read_bytes();assert b'fixture 224' in content and b'fixture 0' in content
        assert b'<button' not in content
        if kind=='csv':
            records=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))));assert len(records)==226 and records[0][0]=='会员ID' and 'Id' not in records[0]
        if kind=='xml':assert 'fixture <>& 0' in ''.join(ET.fromstring(content).itertext())
    page.locator('.game-user-columns summary').click();page.locator('[data-column=id]').uncheck();page.locator('[data-column=risk_level]').uncheck();page.locator('.game-user-columns summary').click()
    page.locator('.game-user-export summary').click()
    with page.expect_download() as download:page.locator('[data-export=json]').click()
    exported=json.loads(Path(download.value.path()).read_text(encoding='utf-8-sig'));assert exported['header'][0][0]=='用户账号' and '风险等级' not in exported['header'][0]
    page.locator('[data-action=cards]').click();assert table.locator('article').count()==225 and not table.locator('strong').first.inner_text().endswith(':')
    page.evaluate("location.hash='members'");table.wait_for(state='detached');page.evaluate("location.hash='risk-history'");table.locator('article').first.wait_for()
    page.locator('[data-action=cards]').click();ready(225);assert table.locator('th[data-field=risk_level]').count()==0
    mode['drift']=True;page.locator('#riskHistoryRefresh').click();page.wait_for_function('document.querySelector("#riskHistoryError").textContent.includes("数据已变化")')
    assert table.locator('tbody tr').count()==225;mode['drift']=False;mode['fail']=True
    page.locator('#riskHistoryRefresh').click();page.wait_for_function('document.querySelector("#riskHistoryError").textContent==="fixture unavailable"')
    mode['fail']=False;page.locator('#riskHistoryRefresh').click();ready(225)
    mode['hold']=True;page.locator('#riskHistoryRefresh').click();page.wait_for_timeout(100);assert len(held)==1
    mode['hold']=False;form.locator('[name=username]').fill('fixture 224');submit();ready(1)
    held.pop().fulfill(status=503,json={'detail':'stale error'});page.wait_for_timeout(100);ready(1)
    for width in [1920,1024,390]:
        page.set_viewport_size({'width':width,'height':844});page.wait_for_timeout(50)
        assert page.locator('#riskHistoryHost').evaluate('el=>el.scrollWidth<=el.clientWidth+1'),width
    page.locator('[data-action=cards]').click();assert page.locator('#riskHistoryHost').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path='visual-baseline/verified/risk-history-mobile.png',full_page=True);page.locator('[data-action=cards]').click()
    mode['hold']=True;page.locator('#riskHistoryRefresh').click();page.wait_for_timeout(100);assert len(held)==1
    page.evaluate("location.hash='members'");table.wait_for(state='detached');held.pop().fulfill(status=503,json={'detail':'closed error'})
    page.wait_for_timeout(100);assert 'closed error' not in page.locator('body').inner_text()
    assert not errors,errors;browser.close()
print('Risk history: reference filters/links, sort/paging/All, columns/cards, six exports, retry/stale cleanup and responsive checks passed')
