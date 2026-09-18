"""Ledger controls, query semantics, downloads and request lifecycle with fixtures."""
import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    rows=[{'id':9100+i,'user_id':8100+i,'username':'fixture '+str(i),'game_id':6100+i,'game_name':'fixture game '+str(i),
           'agent_id':7100+i,'agent_name':'fixture agent '+str(i),'game_ad_status':0,'coin_before':100+i,
           'coin':i-100,'coin_after':i*2,'type':[10,30,40,50,60,70,80,100][i%8],
           'remark':'fixture <>& '+str(i),'created_at':'2026-09-18T00:00:00Z'} for i in range(225)]
    reads=[];held=[];errors=[];state={'fail':False,'hold':False,'drift':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        request=route.request;url=urlparse(request.url);path=url.path.split('/api/')[-1].removeprefix('v1/');q=parse_qs(url.query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert request.method=='GET',path
        if path.startswith('member-filter-options/'):
            is_game=path.endswith('/games');base=6100 if is_game else 7100
            options=[{'id':base+i,'name':('fixture game ' if is_game else 'fixture agent ')+str(i)} for i in range(225)]
            if 'id' in q:options=[r for r in options if str(r['id'])==q['id'][0]]
            if 'q' in q:options=[r for r in options if q['q'][0] in r['name']]
            offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
            route.fulfill(json={'items':options[offset:offset+limit],'total':len(options)});return
        if path!='coin-logs':route.fulfill(json={'items':[],'total':0});return
        reads.append(q)
        if state['hold']:held.append(route);return
        if state['fail']:route.fulfill(status=503,json={'detail':'fixture unavailable'});return
        items=list(rows)
        for key in ['user_id','type','game_id','agent_id','game_ad_status']:
            if key in q:items=[r for r in items if str(r[key])==q[key][0]]
        for key in ['username','remark','agent_name']:
            if key in q:items=[r for r in items if q[key][0] in r[key]]
        if 'game_name_exact' in q:items=[r for r in items if r['game_name']==q['game_name_exact'][0]]
        items.sort(key=lambda r:r[q.get('sort',['id'])[0]],reverse=q.get('order',['desc'])[0]=='desc')
        offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
        route.fulfill(json={'items':items[offset:offset+limit],'total':len(items)+(1 if state['drift'] and offset else 0),'summary':{'change':sum(r['coin'] for r in items)}})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#coin-logs')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    form=page.locator('#coinFilters');table=page.locator('#coinTable');error=page.locator('#coinError')
    table.locator('tbody tr').first.wait_for()
    def ready(count=10):
        page.wait_for_function('(n)=>document.querySelector("#coinTable tbody")?.rows.length===n&&!document.querySelector("#coinTable").hasAttribute("aria-busy")',arg=count)
        assert error.inner_text()=='',error.inner_text()
    def submit():
        form.evaluate('f=>f.requestSubmit()')
    def reset():
        form.locator('[type=reset]').click();ready()
    ready();assert table.locator('th').count()==11 and reads[-1]['limit']==['10']
    assert reads[-1]['game_ad_status']==['0'] and 'created_from' in reads[-1]
    assert page.locator('#coinSummary span').inner_text()==str(sum(r['coin'] for r in rows))
    assert table.locator('[data-sort=id]').count()==0
    # Name links preserve the reference name query instead of substituting one ID.
    table.locator('[data-coin-search=game_name]').first.click();ready(1)
    assert reads[-1]['game_name_exact']==['fixture game 224'] and 'game_id' not in reads[-1]
    assert form.locator('[data-filter-lookup=game_id]').input_value()=='fixture game 224'
    reset();assert 'game_name_exact' not in reads[-1] and form.locator('[data-filter-lookup=game_id]').input_value()==''
    # Selecting an option uses its ID; clicking a name afterwards switches back to name matching.
    lookup=form.locator('[data-filter-lookup=game_id]');lookup.click()
    page.locator('.member-lookup-results:visible .sp_results li').first.wait_for()
    page.locator('.member-lookup-results:visible .sp_results li').first.click();submit();ready(1)
    assert reads[-1]['game_id']==['6100'] and 'game_name_exact' not in reads[-1]
    table.locator('[data-coin-search=game_name]').first.click();ready(1)
    assert reads[-1]['game_name_exact']==['fixture game 0'] and 'game_id' not in reads[-1]
    reset()
    table.locator('[data-coin-search=agent_name]').first.click();ready(1)
    assert reads[-1]['agent_name']==['fixture agent 224'] and 'agent_id' not in reads[-1]
    reset()
    table.locator('[data-coin-search=user_id]').first.click();ready(1);assert reads[-1]['user_id']==['8324']
    reset();table.locator('[data-coin-search=type]').first.click();ready();assert reads[-1]['type']==['10']
    reset();page.locator('[data-action=search]').click();assert not form.is_visible()
    page.locator('[data-action=search]').click();assert form.is_visible()
    form.locator('[name=created_range]').fill('2026-02-30 00:00:00 - 2026-03-02 00:00:00');count=len(reads);submit()
    page.wait_for_function('document.querySelector("#coinError").textContent!==""');assert len(reads)==count
    reset();form.locator('[name=created_range]').click();page.locator('.daterangepicker:visible').wait_for()
    page.keyboard.press('Escape');form.locator('[name=username]').click()
    page.locator('#coinPagination [aria-label="下一页"]').click();ready();assert reads[-1]['offset']==['10']
    for order in ['desc','asc']:
        table.locator('[data-sort=coin]').click();ready()
        assert reads[-1]['sort']==['coin'] and reads[-1]['offset']==['0'] and reads[-1]['order']==[order]
        assert table.locator('[data-sort=coin]').evaluate('async el=>{const i=new Image();i.src=getComputedStyle(el).backgroundImage.slice(5,-2);await i.decode();return i.naturalWidth===19&&i.naturalHeight===19;}')
    page.locator('#coinPagination .game-page-size summary').click();page.locator('[data-game-size=All]').click();ready(225)
    assert reads[-2]['limit']==['200'] and reads[-1]['offset']==['200']
    # Columns, card view and sorting survive re-entry into the route.
    page.locator('.game-user-columns summary').click();page.locator('[data-column=game_ad_status]').check()
    page.locator('[data-column=remark]').uncheck();page.locator('.game-user-columns summary').click()
    assert table.locator('th[data-field=game_ad_status]').count()==1 and table.locator('th[data-field=remark]').count()==0
    table.locator('[data-coin-search=game_ad_status]').first.click();ready(225)
    page.locator('[data-action=cards]').click();assert table.locator('article').count()==225
    page.evaluate("location.hash='members'");table.wait_for(state='detached')
    page.evaluate("location.hash='coin-logs'");table.locator('article').first.wait_for()
    page.locator('[data-action=cards]').click();ready(225)
    assert table.locator('th[data-field=remark]').count()==0
    page.locator('.game-user-columns summary').click();page.locator('[data-column=remark]').check();page.locator('.game-user-columns summary').click()
    # Every format downloads filtered, sorted rows including special characters.
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        content=Path(download.value.path()).read_bytes()
        assert b'fixture 0' in content and b'fixture 224' in content,kind
        assert b'<button' not in content,kind
        if kind=='xml':assert 'fixture <>& 0' in ''.join(ET.fromstring(content).itertext())
        if kind=='csv':
            records=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))
            assert len(records)==226 and records[0][0]=='会员ID' and 'Id' not in records[0]
    state['drift']=True;page.locator('#coinRefresh').click()
    page.wait_for_function('document.querySelector("#coinError").textContent.includes("数据已变化")')
    assert table.locator('tbody tr').count()==225
    state['drift']=False;state['fail']=True;page.locator('#coinRefresh').click()
    page.wait_for_function('document.querySelector("#coinError").textContent==="fixture unavailable"')
    state['fail']=False;page.locator('#coinRefresh').click();ready(225)
    # Older failures cannot replace a fresh successful query.
    state['hold']=True;page.locator('#coinRefresh').click();page.wait_for_timeout(100);assert len(held)==1
    state['hold']=False;form.locator('[name=username]').fill('fixture 224');submit();ready(1)
    held.pop().fulfill(status=503,json={'detail':'stale error'});page.wait_for_timeout(100);ready(1)
    for width in [1920,1024,390]:
        page.set_viewport_size({'width':width,'height':844});page.wait_for_timeout(50)
        assert page.locator('#coinHost').evaluate('el=>el.scrollWidth<=el.clientWidth+1'),width
    page.screenshot(path='visual-baseline/verified/coin-logs-mobile.png',full_page=True)
    page.locator('[data-action=cards]').click();assert not table.locator('strong').first.inner_text().endswith(':')
    assert page.locator('#coinHost').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.locator('[data-action=cards]').click()
    state['hold']=True;page.locator('#coinRefresh').click();page.wait_for_timeout(100);assert len(held)==1
    page.evaluate("location.hash='members'");table.wait_for(state='detached')
    held.pop().fulfill(status=503,json={'detail':'closed error'});page.wait_for_timeout(100)
    assert 'closed error' not in page.locator('body').inner_text()
    assert not errors,errors
    browser.close()
print('Ledger: names, defaults, dates, sort/pagination/All, columns/cards, six exports, retry/stale cleanup and responsive checks passed')
