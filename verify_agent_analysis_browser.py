"""Analysis workflows, chart lifecycle and settings use isolated HTTP fixtures."""
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

fixture=json.loads(Path('visual-baseline/fixtures/agent-analysis/fixture.json').read_text(encoding='utf-8'))
rows=[{**fixture['items'][i%3],'id':i+1,'coin_user':i+1,'coin_user_total':i+1,'coin_every':(i%10)+.5,'success_percent':50 if i%2 else 100,'app_num':i%3+1} for i in range(225)]
settings={};reads=[];writes=[];held=[];errors=[];mode={'fail':None,'hold':None,'configure':True}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    page.add_init_script("sessionStorage.setItem('agent-dashboard-id','9000')")
    page.on('pageerror',lambda error:errors.append(str(error)))
    def api(route):
        request=route.request;path=urlparse(request.url).path.removeprefix('/api/').removeprefix('v1/');q=parse_qs(urlparse(request.url).query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        kind='analysis' if path.endswith('/analysis') else 'settings' if path.endswith('/analysis-settings') else 'member' if path.startswith('members/') else None
        if request.method!='GET':
            assert kind in ('settings','member') and request.method=='PATCH',request.url
            writes.append({'path':path,'body':request.post_data_json});kind='save' if kind=='settings' else 'toggle'
        if kind=='analysis':reads.append({'path':path,'query':q})
        if kind and mode['hold']==kind:held.append(route);return
        if kind and mode['fail']==kind:route.fulfill(status=503,json={'detail':'fixture unavailable'});return
        if kind in ('settings','save'):
            config=settings.setdefault(path,dict(coin=[],success=[],apps=[]))
            if kind=='save':config.update(request.post_data_json)
            route.fulfill(json=config);return
        if kind in ('member','toggle'):
            row=next(row for row in rows if row['id']==int(path.split('/')[1]))
            if kind=='toggle':row.update(request.post_data_json)
            route.fulfill(json=row);return
        if kind=='analysis':
            items=list(rows)
            for key in ['coin_user_total','coin_every','success_percent','app_num']:
                for suffix,compare in [('min',lambda a,b:a>=b),('max',lambda a,b:a<=b)]:
                    if key+'_'+suffix in q:items=[row for row in items if compare(row[key],float(q[key+'_'+suffix][0]))]
            items.sort(key=lambda row:row[q.get('sort',['id'])[0]],reverse=q.get('order',['desc'])[0]=='desc')
            offset=int(q.get('offset',['0'])[0]);limit=int(q.get('limit',['10'])[0])
            route.fulfill(json={**fixture,'agent_name':'Fixture '+path.split('/')[1],'total':len(items),'items':items[offset:offset+limit],'can_configure':mode['configure']});return
        route.fulfill(json={'items':[],'total':0})
    page.route('**/api/**',api);page.goto('http://127.0.0.1:3000/#agent-analysis')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture');page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    form=page.locator('#agentAnalysisFilters');table=page.locator('#agentAnalysisTable');error=page.locator('#agentAnalysisError')
    def ready(count=10):
        page.wait_for_function('n=>document.querySelector("#agentAnalysisTable tbody")?.rows.length===n&&!document.querySelector("#agentAnalysisTable").hasAttribute("aria-busy")',arg=count)
        page.wait_for_function('document.querySelectorAll("[data-analysis-chart] canvas").length===6')
        assert error.inner_text()=='',error.inner_text()
    def submit():form.evaluate('f=>f.requestSubmit()')
    def reset(count=10):form.locator('[type=reset]').click();ready(count)
    def graphs():return page.evaluate("[...document.querySelectorAll('[data-analysis-chart]')].map(n=>({key:n.dataset.analysisChart,type:echarts.getInstanceByDom(n).getOption().series[0].type,data:echarts.getInstanceByDom(n).getOption().series[0].data}))")
    ready();assert len(graphs())==6 and [row['type'] for row in graphs()]==['pie','pie','pie','pie','bar','scatter']
    page.evaluate("echarts.getInstanceByDom(document.querySelector('[data-analysis-chart=coin]')).dispatchAction({type:'showTip',seriesIndex:0,dataIndex:0})")
    page.wait_for_function("document.querySelector('[data-analysis-chart=coin]').textContent.includes('Low')")
    page.evaluate("echarts.getInstanceByDom(document.querySelector('[data-analysis-chart=coin]')).dispatchAction({type:'hideTip'})")
    assert table.locator('th').count()==14 and form.is_visible()
    assert not page.locator('.agent-analysis .ads-toolbar').is_visible()
    assert not page.locator('.agent-region-map').count()
    # The current chart instances must be disposed before each replacement and on navigation.
    page.evaluate("window.oldCharts=[...document.querySelectorAll('[data-analysis-chart]')].map(n=>echarts.getInstanceByDom(n))")
    form.locator('[name=coin_user_total_min]').fill('10');form.locator('[name=coin_user_total_max]').fill('15');submit();ready(6)
    assert page.evaluate('oldCharts.every(chart=>chart.isDisposed())')
    assert reads[-1]['query']['coin_user_total_min']==['10'];reset()
    form.locator('[name=coin_every_min]').fill('1.5');form.locator('[name=success_percent_max]').fill('50');form.locator('[name=app_num_max]').fill('2');submit();ready()
    assert all(row['path']=='agents/9000/analysis' for row in reads)
    form.locator('[name=created_range]').fill('2040-01-01 08:00:00 - 2040-01-02 08:00:00');submit();ready();assert reads[-1]['query']['created_from']==['2040-01-01T00:00:00.000Z']
    for field,value,message in [('coin_every_min','NaN','筛选范围无效'),('success_percent_max','101','筛选范围无效'),('app_num_max','1.5','筛选范围无效'),('created_range','2040-02-30 00:00:00 - 2040-03-01 00:00:00','时间范围无效')]:
        reset();count=len(reads);form.locator('[name='+field+']').fill(value);submit();expect(error).to_contain_text(message);assert len(reads)==count
    reset()
    for key in ['coin_user','coin','freeze_coin','created_at']:
        for order in ['desc','asc']:
            table.locator('[data-sort='+key+']').click();ready();assert reads[-1]['query']['sort']==[key] and reads[-1]['query']['order']==[order]
    page.locator('#agentAnalysisPagination [aria-label="上一页"]').click();ready(5);assert reads[-1]['query']['offset']==['220']
    page.locator('#agentAnalysisPagination [aria-label="下一页"]').click();ready()
    page.locator('#agentAnalysisPagination input').fill('5');page.locator('[data-game-jump]').click();ready();assert reads[-1]['query']['offset']==['40']
    page.locator('#agentAnalysisPagination .game-page-size summary').click();page.locator('[data-game-size=All]').click();ready(225)
    assert reads[-2]['query']['limit']==['200'] and reads[-1]['query']['offset']==['200']
    form.locator('[name=coin_user_total_min]').fill('9999');submit();ready(1);expect(table).to_contain_text('没有找到匹配的记录');reset(225)
    # Member toggle errors preserve the row; success refreshes the scoped analysis.
    button=table.locator('[data-analysis-toggle=is_white]').first;mode['fail']='toggle';button.click();expect(error).to_have_text('fixture unavailable')
    mode['fail']=None;button.click();ready(225);assert writes[-1]['path'].startswith('members/')
    table.locator('[data-analysis-coins]').first.click();expect(page.locator('.game-coin-dialog [name=coin]')).to_be_enabled();page.locator('.game-coin-dialog header button').click()
    table.locator('[data-analysis-edit]').first.click();expect(page.locator('#modal')).to_be_visible();page.locator('#closeModal').click()
    # Configuration append/remove/reset, duplicate lock, persisted values and retry.
    page.locator('[data-analysis-settings=coin]').click();dialog=page.locator('.agent-analysis-settings');dialog.locator('form').wait_for()
    dialog.locator('[data-bucket-add]').click();row=dialog.locator('.analysis-setting-row');row.locator('[name=name]').fill('Small');row.locator('[name=minimum]').fill('0');row.locator('[name=maximum]').fill('10')
    dialog.locator('[data-bucket-add]').click();dialog.locator('.analysis-setting-row').last.locator('[aria-label=删除]').click();expect(row).to_have_count(1)
    dialog.locator('[data-bucket-add]').click();second=dialog.locator('.analysis-setting-row').last
    second.locator('[name=name]').fill('Second');second.locator('[name=minimum]').fill('20');second.locator('[name=maximum]').fill('30')
    second.locator('[data-bucket-move]').focus();page.keyboard.press('ArrowUp');expect(dialog.locator('.analysis-setting-row').first.locator('[name=name]')).to_have_value('Second')
    dialog.locator('.analysis-setting-row').first.locator('[aria-label=删除]').click()
    dialog.locator('[data-agent-oss-minimize]').click();assert dialog.bounding_box()['height']==45
    dialog.locator('[data-agent-oss-maximize]').click();dialog.locator('[data-agent-oss-maximize]').click();assert dialog.bounding_box()['width']==1920
    dialog.locator('[data-agent-oss-maximize]').click();assert dialog.bounding_box()['width']==800
    mode['fail']='save';dialog.locator('form').evaluate('f=>f.requestSubmit()');expect(dialog.locator('[role=alert]')).to_have_text('fixture unavailable')
    mode['fail']=None;mode['hold']='save';dialog.locator('form').evaluate('f=>f.requestSubmit()');page.wait_for_timeout(80);assert held;count=len(writes)
    dialog.locator('form').evaluate('f=>f.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))');assert len(writes)==count
    expect(row.locator('[name=name]')).to_be_disabled();mode['hold']=None;held.pop().fulfill(json={});dialog.wait_for(state='detached');ready(225)
    page.locator('[data-analysis-settings=coin]').click();dialog.locator('form').wait_for();dialog.locator('[data-bucket-add]').click()
    row.locator('[name=name]').fill('Small');row.locator('[name=minimum]').fill('0');row.locator('[name=maximum]').fill('10');dialog.locator('form').evaluate('f=>f.requestSubmit()');dialog.wait_for(state='detached');ready(225)
    assert list(writes[-1]['body'])==['coin']
    page.locator('[data-analysis-settings=coin]').click();expect(row.locator('[name=name]')).to_have_value('Small');row.locator('[name=name]').fill('Changed');dialog.locator('[type=reset]').click();expect(row.locator('[name=name]')).to_have_value('Small');page.keyboard.press('Escape');dialog.wait_for(state='detached')
    mode['fail']='settings';page.locator('[data-analysis-settings=success]').click();expect(dialog.locator('[role=alert]')).to_have_text('fixture unavailable');mode['fail']=None;dialog.locator('main button').click();dialog.locator('form').wait_for();page.keyboard.press('Escape');dialog.wait_for(state='detached')
    # Old read and chart callbacks cannot overwrite a new agent or page.
    mode['hold']='analysis';submit();page.wait_for_timeout(80);assert held
    page.evaluate("location.hash='book'");page.locator('#tutorialHost').wait_for();mode['hold']=None
    held.pop().fulfill(status=503,json={'detail':'stale analysis'});page.wait_for_timeout(80);assert 'stale analysis' not in page.locator('body').inner_text()
    page.evaluate("sessionStorage.setItem('agent-dashboard-id','9001');location.hash='agent-analysis'");ready(225)
    expect(page.locator('#agentAnalysisName')).to_have_text('代理商名称：Fixture 9001');assert reads[-1]['query']['limit']==['200']
    assert not any(key.endswith(('_min','_max')) for key in reads[-1]['query'])
    page.locator('#agentAnalysisPagination .game-page-size summary').click();page.locator('[data-game-size="10"]').click();ready()
    mode['configure']=False;submit();ready();expect(page.locator('[data-analysis-settings=coin]')).to_be_disabled();mode['configure']=True;submit();ready()
    # Responsive chart sizing, nonblank canvases and tooltips.
    for width in [1920,1024,390]:
        page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(150)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        assert page.evaluate("[...document.querySelectorAll('[data-analysis-chart] canvas')].every(n=>{const p=n.getContext('2d').getImageData(0,0,n.width,n.height).data;return p.some((v,i)=>i%4===3&&v>0)})")
        page.evaluate('scrollTo(0,0)');page.screenshot(path=f'visual-baseline/verified/agent-analysis-{width}.png',full_page=True)
        page.locator('[data-analysis-settings=apps]').click();dialog.locator('form').wait_for();dialog.locator('[data-bucket-add]').click()
        box=dialog.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width
        assert dialog.evaluate('n=>n.scrollWidth<=n.clientWidth');page.keyboard.press('Escape');dialog.wait_for(state='detached')
    mode['fail']='analysis';submit();expect(error).to_have_text('fixture unavailable');mode['fail']=None;submit();ready()
    assert not errors,errors
    print(json.dumps({'passed':True,'requests':len(reads),'writes':len(writes),'charts':6,'widths':[1920,1024,390]}))
    browser.close()
