"""Agent list and OSS workflows with synthetic browser responses only."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

rows = [{'id': i+1, 'name': 'Fixture <>& '+str(i), 'parent_id': 1 if i % 3 == 0 else 0, 'status': i % 2,
    'user_id': 100+i, 'role_id': 200+i, 'security_key': 'synthetic-key',
    'created_at': (datetime(2040, 1, 1, tzinfo=timezone.utc)+timedelta(minutes=i % 3)).isoformat(),
    'updated_at': (datetime(2040, 1, 2, tzinfo=timezone.utc)+timedelta(minutes=i % 2)).isoformat()} for i in range(225)]
permissions = dict(create=True, edit=True, delete=True, oss=True, batch_status=True, dashboard=True)
config = dict(ossKey='synthetic-key',ossKeySecret='synthetic-secret',endPoint='https://fixture.invalid',bucket='fixture-bucket')
reads=[];writes=[];held=[];errors=[];mode=dict(hold=None,fail=None,drift=False)
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        request=route.request;url=urlparse(request.url);path=url.path.removeprefix('/api/').removeprefix('v1/');q=parse_qs(url.query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        kind='list' if path=='agents' else 'batch' if path=='agents/batch-status' else 'oss' if path.endswith('/oss') else None
        if request.method!='GET':
            assert kind in ('batch','oss') and request.method in ('PATCH','POST'),request.url
            writes.append({'path':path,'body':request.post_data_json});kind='save' if kind=='oss' else kind
        if kind=='list':reads.append(q)
        if kind and mode['hold']==kind:held.append(route);return
        if kind and mode['fail']==kind:route.fulfill(status=503,json={'detail':'fixture unavailable'});return
        if kind=='batch':
            body=request.post_data_json
            for row in rows:
                if row['id'] in body['ids']:row['status']=body['status']
            route.fulfill(json={'updated':len(body['ids'])});return
        if kind=='save':config.update(request.post_data_json);route.fulfill(json={'saved':True});return
        if kind=='oss':route.fulfill(json=config);return
        if kind=='list':
            items=list(rows)
            for key in ('name','status'):
                if key in q:items=[row for row in items if q[key][0] in str(row[key])]
            for field in ['created','updated']:
                for suffix,op in [('from',lambda a,b:a>=b),('to',lambda a,b:a<=b)]:
                    if field+'_'+suffix in q:
                        boundary=datetime.fromisoformat(q[field+'_'+suffix][0])
                        items=[row for row in items if op(datetime.fromisoformat(row[field+'_at']),boundary)]
            items.sort(key=lambda r:r['id'],reverse=True)
            items.sort(key=lambda r:r[q.get('sort',['id'])[0]],reverse=q.get('order',['desc'])[0]=='desc')
            offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
            route.fulfill(json={'items':items[offset:offset+limit],'total':len(items)+(1 if offset and mode['drift'] else 0),'permissions':permissions});return
        if path.endswith('/dashboard'):route.fulfill(json={'agent_name':'Fixture','items':[],'today_new':0,'today_login':0});return
        if path.startswith('agents/'):
            route.fulfill(json={**rows[int(path.split('/')[1])-1],'user_name':'fixture-account'});return
        route.fulfill(json={'items':[],'total':0})
    page.route('**/api/**',fixture);page.goto('http://127.0.0.1:3000/#agents')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    form=page.locator('#agentFilters');table=page.locator('#agentList');error=page.locator('#reviewError')
    def ready(count=10):
        page.wait_for_function('n=>document.querySelector("#agentList tbody")?.rows.length===n&&!document.querySelector("#agentList").hasAttribute("aria-busy")',arg=count)
        assert error.inner_text()=='',error.inner_text()
    def submit():form.evaluate('f=>f.requestSubmit()')
    def reset(count=10):form.locator('[type=reset]').click();ready(count)
    def close_oss():page.locator('.agent-oss-dialog [data-agent-oss-close]').click();page.locator('.agent-oss-dialog').wait_for(state='detached')
    ready();assert not form.is_visible() and table.locator('th').count()==7
    assert reads[-1]=={'limit':['10'],'offset':['0'],'sort':['id'],'order':['desc']}
    assert page.locator('#agentCreate').is_visible() and table.locator('[data-edit]').count()==10
    assert table.locator('[data-agent-enter]').count()==7
    # Selection/export only uses selected rows, without operation column.
    table.locator('td[data-field=name]').first.click();expect(table.locator('[data-agent-select]').first).to_be_checked()
    expect(table.locator('#agentSelectAll')).to_have_js_property('indeterminate',True)
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        data=Path(download.value.path()).read_bytes()
        if kind=='json':assert len(json.loads(data)['data'])==1 and json.loads(data)['header'][0]==['Id','代理商名称','游戏管理','状态','创建时间']
        if kind=='xml':assert 'Fixture <>& 224' in ''.join(ET.fromstring(data).itertext())
    table.locator('#agentSelectAll').check();assert table.locator('[data-agent-select]:checked').count()==10
    table.locator('#agentSelectAll').uncheck()
    page.locator('#agentPagination [aria-label="上一页"]').click();ready(5);assert reads[-1]['offset']==['220']
    page.locator('#agentPagination [aria-label="下一页"]').click();ready()
    page.locator('#agentPagination input').fill('5');page.locator('[data-game-jump]').click();ready();assert reads[-1]['offset']==['40']
    page.locator('.game-user-columns summary').click()
    for key in ['user_id','role_id','security_key','updated_at']:page.locator('[data-column='+key+']').check()
    page.locator('.game-user-columns summary').click();assert table.locator('th').count()==11
    assert 'synthetic-key' in table.inner_text()
    for key in ['created_at','updated_at','id']:
        for order in ['desc','asc']:
            table.locator('[data-sort='+key+']').click();ready();assert reads[-1]['sort']==[key] and reads[-1]['order']==[order] and reads[-1]['offset']==['0']
    page.locator('#agentSearchToggle').click();expect(form).to_be_visible()
    form.locator('[name=name]').fill('Fixture <>& 22');form.locator('[name=status]').select_option('1');submit();ready(2)
    assert reads[-1]['name']==['Fixture <>& 22'] and reads[-1]['status']==['1'];reset()
    form.locator('[name=created_range]').fill('2040-01-01 08:01:00 - 2040-01-01 08:01:00')
    form.locator('[name=updated_range]').fill('2040-01-02 08:01:00 - 2040-01-02 08:01:00');submit();ready()
    assert reads[-1]['created_from']==['2040-01-01T00:01:00.000Z'] and reads[-1]['updated_from']==['2040-01-02T00:01:00.000Z']
    page.locator('#agentRefresh').click();ready();assert 'created_from' in reads[-1]
    count=len(reads);form.locator('[name=created_range]').fill('2040-02-30 00:00:00 - 2040-03-01 00:00:00');submit()
    expect(error).to_contain_text('时间范围无效');assert len(reads)==count;reset()
    page.locator('#agentSearchToggle').click();page.locator('#agentPagination .game-page-size summary').click();page.locator('[data-game-size=All]').click();ready(225)
    assert reads[-2]['limit']==['200'] and reads[-1]['offset']==['200']
    for kind in ['json','xml','csv','txt','doc','excel']:
        page.locator('.game-user-export summary').click()
        with page.expect_download() as download:page.locator('[data-export='+kind+']').click()
        data=Path(download.value.path()).read_bytes()
        if kind=='json':assert len(json.loads(data)['data'])==225
        if kind=='xml':assert 'Fixture <>& 0' in ''.join(ET.fromstring(data).itertext())
    # Batch failure, retry, duplicate submission lock, and success refresh.
    table.locator('#agentSelectAll').check();mode['fail']='batch';page.locator('.agent-more summary').click();page.locator('[data-agent-batch="0"]').click()
    expect(error).to_have_text('fixture unavailable');assert table.locator('[data-agent-select]:checked').count()==225
    mode['fail']=None;mode['hold']='batch';page.locator('.agent-more summary').click();page.locator('[data-agent-batch="0"]').click()
    page.wait_for_timeout(80);assert held;count=len(writes)
    page.locator('[data-agent-batch="0"]').evaluate('b=>b.click()');assert len(writes)==count
    mode['hold']=None;held.pop().fulfill(json={'updated':225});ready(225)
    assert not table.locator('[data-agent-select]:checked').count()
    table.locator('#agentSelectAll').check();page.locator('.agent-more summary').click();page.locator('[data-agent-batch="1"]').click();ready(225)
    assert all(row['status']==1 for row in rows)
    # OSS reads/writes remain separate from list credentials. Reset, retries and close guards.
    table.locator('[data-agent-oss]').first.click();dialog=page.locator('.agent-oss-dialog');oss=dialog.locator('form')
    expect(oss.locator('[name=ossKeySecret]')).to_have_value('synthetic-secret')
    assert dialog.bounding_box()['width']==800 and dialog.bounding_box()['height']==600
    page.locator('.agent-oss-dialog').first.locator('[data-agent-oss-minimize]').click()
    table.locator('[data-agent-oss]').nth(1).click();expect(page.locator('.agent-oss-dialog')).to_have_count(2)
    page.locator('.agent-oss-dialog').last.locator('[data-agent-oss-minimize]').click()
    assert page.locator('.agent-oss-dialog').first.bounding_box()['x']==0 and page.locator('.agent-oss-dialog').last.bounding_box()['x']==181
    page.set_viewport_size({'width':320,'height':844});page.wait_for_timeout(80)
    assert page.locator('.agent-oss-dialog').first.bounding_box()['y']!=page.locator('.agent-oss-dialog').last.bounding_box()['y']
    page.keyboard.press('Escape');expect(page.locator('.agent-oss-dialog')).to_have_count(1)
    page.set_viewport_size({'width':1920,'height':1080});dialog.locator('[data-agent-oss-maximize]').click()
    dialog.locator('[data-agent-oss-maximize]').click();assert dialog.bounding_box()['width']==1920
    dialog.locator('[data-agent-oss-maximize]').click();assert dialog.bounding_box()['width']==800
    before=dialog.bounding_box();header=dialog.locator('header').bounding_box()
    page.mouse.move(header['x']+50,header['y']+20);page.mouse.down();page.mouse.move(header['x']+90,header['y']+50);page.mouse.up()
    assert dialog.bounding_box()['x']>before['x'] and dialog.bounding_box()['y']>before['y']
    oss.locator('[name=ossKeySecret]').fill('changed');oss.locator('[type=reset]').click();expect(oss.locator('[name=ossKeySecret]')).to_have_value('synthetic-secret')
    oss.locator('[name=bucket]').fill('changed-bucket');mode['fail']='save';oss.evaluate('f=>f.requestSubmit()');expect(oss.locator('[role=alert]')).to_have_text('fixture unavailable')
    mode['fail']=None;mode['hold']='save';oss.evaluate('f=>f.requestSubmit()');page.wait_for_timeout(80);count=len(writes)
    oss.evaluate('f=>f.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))');assert len(writes)==count
    expect(oss.locator('[name=bucket]')).to_be_disabled();close_oss();mode['hold']=None;held.pop().fulfill(json={'saved':True})
    mode['fail']='oss';table.locator('[data-agent-oss]').first.click();expect(dialog.locator('[role=alert]')).to_have_text('fixture unavailable')
    mode['fail']=None;dialog.locator('[data-agent-oss-retry]').click();oss.locator('[name=bucket]').wait_for()
    oss.locator('[name=bucket]').fill('saved-bucket');oss.evaluate('f=>f.requestSubmit()');dialog.wait_for(state='detached')
    table.locator('[data-agent-oss]').first.click();expect(oss.locator('[name=bucket]')).to_have_value('saved-bucket');page.keyboard.press('Escape');dialog.wait_for(state='detached')
    mode['hold']='oss';table.locator('[data-agent-oss]').first.click();page.wait_for_timeout(80);assert held;close_oss();mode['hold']=None
    held.pop().fulfill(json=config);page.wait_for_timeout(50);assert not dialog.count()
    # Card selection persists across view toggles, but resets on refreshed data.
    table.locator('[data-agent-select]').first.check();page.locator('[data-action=cards]').click()
    expect(table.locator('[data-agent-select]').first).to_be_checked();assert table.locator('article').count()==225
    page.locator('[data-action=cards]').click();ready(225)
    # Isolated account capabilities control visible actions.
    permissions.update(dict(create=False,edit=False,delete=False,oss=False,batch_status=False));page.locator('#agentRefresh').click();ready(225)
    assert not table.locator('[data-edit],[data-delete],[data-agent-oss]').count()
    expect(page.locator('#agentCreate')).not_to_be_visible();expect(page.locator('.agent-more')).not_to_be_visible()
    permissions.update(dict(create=True,edit=True,delete=True,oss=True,batch_status=True));page.locator('#agentRefresh').click();ready(225)
    table.locator('[data-edit]').first.click();expect(page.locator('#modal')).to_be_visible();page.locator('#closeModal').click()
    page.locator('#agentCreate').click();expect(page.locator('#modal')).to_be_visible();page.locator('#closeModal').click()
    # Leaving and returning aborts old lists. Delayed mutation completion cannot refresh another route.
    mode['hold']='list';page.locator('#agentRefresh').click();page.wait_for_timeout(80);assert held
    page.evaluate("location.hash='book'");page.locator('#tutorialHost').wait_for();mode['hold']=None
    page.evaluate("location.hash='agents'");ready(225);held.pop().fulfill(status=503,json={'detail':'stale list'});page.wait_for_timeout(80);assert error.inner_text()==''
    mode['hold']='batch';table.locator('[data-agent-select]').first.check();page.locator('.agent-more summary').click();page.locator('[data-agent-batch="0"]').click();page.wait_for_timeout(80);assert held
    page.evaluate("location.hash='book'");page.locator('#tutorialHost').wait_for();count=len(reads);mode['hold']=None
    held.pop().fulfill(json={'updated':1});page.wait_for_timeout(80);assert len(reads)==count
    page.evaluate("location.hash='agents'");ready(225)
    page.locator('#agentSearchToggle').click();form.locator('[name=name]').fill('No matches');submit();ready(1)
    expect(table).to_contain_text('没有找到匹配的记录');expect(page.locator('#agentPagination')).not_to_be_visible();reset(225)
    page.locator('#agentSearchToggle').click();page.locator('#agentPagination .game-page-size summary').click();page.locator('[data-game-size="10"]').click();ready()
    for width in [1920,1024,390]:
        page.set_viewport_size({'width':width,'height':900});page.locator('#agentSearchToggle').click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        table.locator('[data-agent-oss]').first.click();oss.locator('[name=bucket]').wait_for()
        box=dialog.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width
        page.screenshot(path=f'visual-baseline/verified/agents-{width}.png');close_oss();page.locator('#agentSearchToggle').click()
    mode['fail']='list';page.locator('#agentRefresh').click();expect(error).to_have_text('fixture unavailable')
    mode['fail']=None;page.locator('#agentRefresh').click();ready()
    mode['drift']=True;page.locator('#agentPagination .game-page-size summary').click();page.locator('[data-game-size=All]').click();expect(error).to_contain_text('数据已变化')
    assert not errors,errors
    print(json.dumps({'passed':True,'list_requests':len(reads),'synthetic_writes':len(writes),'widths':[1920,1024,390]}))
    browser.close()
