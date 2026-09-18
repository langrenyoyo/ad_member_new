"""Whitelist workflows with in-memory responses; no business database mutations."""
import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    rows=[{'id':8100+i,'username':'fixture '+str(i),'name':'fixture name '+str(i),'parent_id':8000,'parent_username':'fixture parent','parent_name':'fixture parent',
           'game_id':6100+i,'agent_id':7100+i,'game_name':'fixture game '+str(i),'agent_name':'fixture agent '+str(i),
           'coin_user':100+i,'coin_user_month':10+i,'coin_user_day':i,'coin':10.5+i,'freeze_coin':0,'is_white':1,'status':1,
           'exchange_enable':1,'game_addiction_enable':0,'created_at':'2026-09-18T00:00:00Z'} for i in range(225)]
    rows[-1]['username']='fixture 224 <>&'
    reads=[];writes=[];held=[];errors=[];state={'fail':False,'hold':False,'read_fail':False,'read_hold':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        request=route.request;url=urlparse(request.url);path=url.path.split('/api/')[-1].removeprefix('v1/');q=parse_qs(url.query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        if path.startswith('members/') and path.split('/')[-1].isdigit():
            row=next(r for r in rows if r['id']==int(path.split('/')[-1]))
            if request.method=='GET':route.fulfill(json=row);return
            assert request.method=='PATCH';body=json.loads(request.post_data);writes.append((path,body))
            if state['hold']:held.append(route);return
            if state['fail']:route.fulfill(status=403,json={'detail':'fixture permission denied'});return
            row.update(body);route.fulfill(json=row);return
        assert request.method=='GET',path
        if path.startswith('member-filter-options/'):
            kind='game' if path.endswith('/games') else 'agent';base=6100 if kind=='game' else 7100
            options=[{'id':base+i,'name':'fixture '+kind+' '+str(i)} for i in range(225)]
            if 'id' in q:options=[r for r in options if str(r['id'])==q['id'][0]]
            if 'q' in q:options=[r for r in options if q['q'][0] in r['name']]
            start=int(q.get('offset',['0'])[0]);size=int(q.get('limit',['10'])[0]);route.fulfill(json={'items':options[start:start+size],'total':len(options)});return
        reads.append((path,q))
        if path!='risk/whitelist':route.fulfill(json={'items':[],'total':0});return
        if state['read_hold']:held.append(route);return
        if state['read_fail']:route.fulfill(status=503,json={'detail':'fixture unavailable'});return
        items=[r for r in rows if r['is_white']==1]
        for key in ['parent_id','game_id','agent_id','status']:
            if key in q:items=[r for r in items if str(r[key])==q[key][0]]
        for key in ['username','name','agent_name']:
            if key in q:items=[r for r in items if q[key][0] in r[key]]
        if 'game_name' in q:items=[r for r in items if r['game_name']==q['game_name'][0]]
        items.sort(key=lambda r:r[q.get('sort',['id'])[0]],reverse=q.get('order',['desc'])[0]=='desc')
        start=int(q.get('offset',['0'])[0]);size=int(q.get('limit',['10'])[0]);route.fulfill(json={'items':items[start:start+size],'total':len(items)})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#risk-whitelist')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    table=page.locator('#whitelistTable');form=page.locator('#whitelistFilters');error=page.locator('#whitelistError')
    def ready(count=10):
        page.wait_for_function('n=>document.querySelector("#whitelistTable tbody")?.rows.length===n&&!document.querySelector("#whitelistTable").hasAttribute("aria-busy")',arg=count)
        assert error.inner_text()=='',error.inner_text()
    def query():return next(q for path,q in reversed(reads) if path=='risk/whitelist')
    def reset():form.locator('[type=reset]').click();ready()
    ready();assert not form.is_visible() and table.locator('th').count()==14 and query()['limit']==['10']
    assert table.locator('[data-white-edit]').count()==10 and table.locator('[data-member-behavior]').count()==20
    first=table.locator('[data-white-select]').first;first.check()
    table.locator('tbody tr').nth(1).locator('[data-field=coin]').click()
    page.locator('[data-action=cards]').click();assert table.locator('[data-white-select]:checked').count()==2
    page.locator('[data-action=cards]').click()
    for kind in ['csv','json','xml','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        content=Path(download.value.path()).read_bytes()
        assert b'8324' in content and b'8323' in content and b'8322' not in content
        assert b'<button' not in content
        if kind=='csv':assert len(list(csv.reader(io.StringIO(content.decode('utf-8-sig')))))==3
        if kind=='xml':assert 'fixture 224 <>&' in ''.join(ET.fromstring(content).itertext())
    state['fail']=True;toggle=table.locator('[data-white-toggle=status]').first;toggle.click()
    page.wait_for_function('document.querySelector("#whitelistError").textContent.includes("permission denied")')
    assert toggle.get_attribute('aria-checked')=='true' and table.locator('[data-white-select]:checked').count()==2
    state['fail']=False;toggle.click()
    page.wait_for_function('document.querySelector("[data-white-toggle=status]").getAttribute("aria-checked")==="false"');ready()
    assert table.locator('[data-white-select]:checked').count()==0
    table.locator('[data-white-search=game_name]').first.click();ready(1)
    assert form.is_visible() and query()['game_name']==['fixture game 224'] and 'game_id' not in query()
    reset();assert 'game_name' not in query()
    form.locator('[data-filter-lookup=game_id]').click();page.locator('.member-lookup-results:visible .sp_results li').first.click()
    form.evaluate('f=>f.requestSubmit()');ready(1);assert query()['game_id']==['6100']
    reset()
    form.locator('[name=created_range]').fill('2026-02-30 00:00:00 - 2026-03-01 00:00:00');count=len(reads);form.evaluate('f=>f.requestSubmit()')
    page.wait_for_function('document.querySelector("#whitelistError").textContent!==""');assert len(reads)==count
    reset();form.locator('[name=created_range]').click();page.locator('.daterangepicker:visible').wait_for();form.locator('[name=username]').click()
    # Row behavior windows retain the member and single/multiple game scope.
    table.locator('[data-member-behavior=single]').first.click();dialog=page.locator('.member-behavior-dialog');dialog.wait_for()
    page.wait_for_timeout(100);assert any(path=='lottery-records' and q.get('user_id')==['8324'] and q.get('game_id')==['6324'] for path,q in reads)
    dialog.locator('[data-behavior-close]').click()
    table.locator('[data-member-behavior=multiple]').first.click();dialog.wait_for();page.wait_for_timeout(100)
    assert any(path=='lottery-records' and q.get('user_id')==['8324'] and q.get('filter_user_id')==['8324'] and 'game_id' not in q for path,q in reads)
    dialog.locator('[data-behavior-close]').click()
    # Existing member editor and coin dialog are reachable and persist real field changes.
    table.locator('[data-white-edit]').first.click();page.locator('#formFields [name=name]').wait_for(state='visible')
    page.locator('#formFields [name=name]').fill('edited fixture')
    page.locator('#editorForm').evaluate('f=>f.requestSubmit()');page.locator('#modal').wait_for(state='hidden');ready()
    assert rows[-1]['name']=='edited fixture'
    table.locator('[data-white-coins]').first.click();coin=page.locator('#memberCoinDialog');coin.locator('[type=submit]:enabled').wait_for()
    coin.locator('[name=coin]').fill('77.5');coin.locator('[type=submit]').click();coin.wait_for(state='detached');ready()
    assert rows[-1]['coin']==77.5 and form.is_visible()
    page.locator('#whitelistPagination [aria-label="下一页"]').click();ready();assert query()['offset']==['10']
    table.locator('[data-sort=coin]').click();ready();assert query()['sort']==['coin'] and query()['offset']==['0']
    page.locator('.game-user-columns summary').click();page.locator('[data-column=exchange_enable]').check();page.locator('[data-column=agent_name]').check();page.locator('.game-user-columns summary').click()
    assert table.locator('[data-white-toggle=exchange_enable]').count()==10
    table.locator('[data-white-search=agent_name]').first.click();ready(1);assert 'agent_name' in query() and 'agent_id' not in query()
    reset();page.locator('#whitelistPagination .game-page-size summary').click();page.locator('[data-game-size=All]').click();ready(225)
    assert query()['offset']==['200'] and query()['limit']==['200']
    # Removing white status removes only membership, not the member or its balances.
    target=table.locator('[data-white-toggle=is_white]').first;removed=int(target.get_attribute('data-white-id'));target.click();ready(224)
    assert len(rows)==225 and next(r for r in rows if r['id']==removed)['is_white']==0
    state['read_fail']=True;page.locator('#whitelistRefresh').click()
    page.wait_for_function('document.querySelector("#whitelistError").textContent==="fixture unavailable"');assert table.locator('tbody tr').count()==224
    state['read_fail']=False;page.locator('#whitelistRefresh').click();ready(224)
    state['hold']=True;table.locator('[data-white-toggle=status]').first.click();page.wait_for_timeout(100);assert len(held)==1
    form.locator('[name=username]').fill('fixture 224');form.evaluate('f=>f.requestSubmit()');ready(1)
    count=len(reads);held.pop().fulfill(status=403,json={'detail':'stale permission error'});page.wait_for_timeout(100)
    assert len(reads)==count and error.inner_text()=='';state['hold']=False
    for width in [1920,1024,390]:
        page.set_viewport_size({'width':width,'height':844});page.wait_for_timeout(50)
        assert page.locator('#whitelistHost').evaluate('el=>el.scrollWidth<=el.clientWidth+1'),width
    page.locator('[data-action=cards]').click();assert table.locator('article').count()==1
    assert page.locator('#whitelistHost').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path='visual-baseline/verified/whitelist-mobile.png',full_page=True)
    page.locator('[data-action=cards]').click()
    state['read_hold']=True;page.locator('#whitelistRefresh').click();page.wait_for_timeout(100);assert len(held)==1
    page.evaluate("location.hash='members'");table.wait_for(state='detached')
    held.pop().fulfill(status=503,json={'detail':'closed failure'});state['read_hold']=False
    page.evaluate("location.hash='risk-whitelist'");ready(1);assert form.is_visible() and 'closed failure' not in page.locator('body').inner_text()
    assert not errors,errors
    browser.close()
print('Whitelist: selection/export, names, switches/retry, member/coin/behavior dialogs, All, stale scope and mobile passed')
