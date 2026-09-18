"""Exercise the real dialog code with controlled history records; no business writes."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1920,'height':1080}, accept_downloads=True)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.goto('http://127.0.0.1:3000/#games', wait_until='networkidle')
    page.locator('[data-game-user]').first.wait_for()
    game_id = int(page.locator('[data-game-user]').first.get_attribute('data-game-user'))
    page.evaluate("localStorage.setItem('pagesize','10')")
    calls=[]
    count={'value':23,'fail':False}
    def history(route):
        url=urlparse(route.request.url)
        query={k:v[0] for k,v in parse_qs(url.query).items()}
        calls.append((url.path,query))
        assert f'/games/{game_id}/' in url.path
        if count['fail']:
            count['fail']=False
            route.fulfill(status=503,json={'detail':'测试服务暂时不可用'})
            return
        is_login=url.path.endswith('login-logs')
        rows=[dict(id=i,user_id=900+i,username=f'user-{i}',game_name='fixture game',device_id=f'device-{i}',
                   ip='192.0.2.1',created_at=f'2025-01-{(i-1)%28+1:02d}T16:00:00',lottery_price=i*5,
                   ecpm=3.5,adn_name='fixture',network_status=0,status=1,is_white=1,tag='<script>bad()</script>',
                   ad_network_rit_id='rit',request_id=f'request-{i}',trans_id=f'trans-{i}') for i in range(1,count['value']+1)]
        for key in ['user_id','username','ip','network_status','status','is_white','adn_name']:
            if key in query: rows=[row for row in rows if (query[key] in row[key] if key=='username' else str(row[key])==query[key])]
        rows.sort(key=lambda row:row[query['sort']],reverse=query['order']=='desc')
        total=len(rows);offset=int(query['offset']);limit=int(query['limit'])
        route.fulfill(json={'total':total,'items':rows[offset:offset+limit],'limit':limit,'offset':offset})
    page.route('**/api/v1/games/*/lottery-records?*', history)
    page.route('**/api/v1/games/*/login-logs?*', history)
    page.locator('[data-game-user]').first.click()
    dialog=page.locator('.game-user-dialog')
    assert dialog.locator('[role=tab]').count()==7
    assert dialog.get_attribute('aria-label')
    first=page.locator('#game-user-pane-first')
    five=page.locator('#game-user-pane-five')
    first.locator('tbody tr').first.wait_for()
    assert first.locator('tbody tr').count()==10
    assert first.locator('tbody tr').first.locator('td').first.inner_text()=='23'
    assert first.locator('tbody script').count()==0
    assert '<script>bad()</script>' in first.inner_text()
    for tab,endpoint in [('second','/risk/history'),('four','/members')]:
        with page.expect_response(lambda response: endpoint+'?' in response.url and f'game_id={game_id}' in response.url) as response:
            page.locator(f'[data-tab={tab}]').click()
        assert response.value.status==200
        pane=page.locator(f'#game-user-pane-{tab}')
        pane.locator('tbody').wait_for()
        pane.locator('[data-action=search]').click()
        pane.locator('[name=created_range]').fill('2025-01-01 00:00:00 - 2025-01-02 00:00:00')
        page.wait_for_selector('.game-user-dialog .daterangepicker:visible',state='visible')
        page.keyboard.press('Escape')
        field='network_status' if tab=='second' else 'is_true'
        pane.locator(f'[name={field}]').select_option('0')
        with page.expect_response(lambda response: endpoint+'?' in response.url and field+'=0' in response.url and 'created_from=' in response.url) as response:
            pane.locator('[type=submit]').click()
        assert response.value.status==200
        sort='created_at' if tab=='second' else 'coin'
        with page.expect_response(lambda response: endpoint+'?' in response.url and f'sort={sort}' in response.url) as response:
            pane.locator(f'[data-sort={sort}]').click()
        assert response.value.status==200
    page.locator('[data-tab=third]').click()
    third=page.locator('#game-user-pane-third')
    third.locator('tbody').wait_for()
    third.locator('[data-action=search]').click()
    assert third.locator('[name=created_range]').count()==1
    third.locator('[name=created_range]').fill('2025-01-01 00:00:00 - 2025-01-02 00:00:00')
    page.keyboard.press('Escape')
    with page.expect_response(lambda r: '/withdrawals?' in r.url and 'created_from=' in r.url) as response:
        third.locator('[type=submit]').click()
    assert response.value.status==200
    page.locator('[data-tab=six]').click()
    six=page.locator('#game-user-pane-six')
    six.locator('tbody').wait_for()
    six.locator('[data-action=search]').click()
    six.locator('[name=date_range]').fill('2025-01-01 00:00:00 - 2025-01-02 23:59:59')
    page.keyboard.press('Escape')
    with page.expect_response(lambda r: '/daily-activity?' in r.url and 'date_from=2025-01-01' in r.url) as response:
        six.locator('[type=submit]').click()
    assert response.value.status==200
    page.locator('[data-tab=seven]').click()
    stats=page.locator('#game-user-pane-seven')
    stats.locator('.game-stat-cards').wait_for()
    assert all(actual.startswith(expected) for actual,expected in zip(stats.locator('.game-stat-cards article>div').all_text_contents(),['总金额','本年金额','上月金额','本月金额','昨日金额']))
    assert stats.locator('.game-stat-counters span').all_text_contents()==['总会员数','今日新增','今日登陆']
    page.wait_for_function("document.querySelectorAll('#game-user-pane-seven canvas').length===4")
    chart_state=stats.evaluate('''el=>Array.from(el.querySelectorAll('[data-stat-chart]')).map(node=>{
      const option=echarts.getInstanceByDom(node).getOption();return {names:option.series.map(s=>s.name),type:option.series.map(s=>s.type)};
    })''')
    assert chart_state[0]['names']==['预估收益API','点击量','金币','日活']
    assert chart_state[0]['type']==['line','line','bar','bar']
    by_chart={node['key']:node for node in stats.evaluate('''el=>Array.from(el.querySelectorAll('[data-stat-chart]')).map(node=>({key:node.dataset.statChart,option:echarts.getInstanceByDom(node).getOption()})).map(row=>({key:row.key,names:row.option.series.map(s=>s.name),type:row.option.series.map(s=>s.type)}))''')}
    assert by_chart['registrations']['names']==['注册用户数']
    page.evaluate("()=>{window.testStatCharts=Array.from(document.querySelectorAll('[data-stat-chart]')).map(el=>echarts.getInstanceByDom(el));}")
    page.evaluate("()=>{testStatCharts[0].dispatchAction({type:'legendToggleSelect',name:'金币'});}")
    assert page.evaluate("testStatCharts[0].getOption().legend[0].selected['金币']===false")
    page.evaluate("()=>{testStatCharts[0].dispatchAction({type:'legendToggleSelect',name:'金币'});}")
    stats.locator('[data-stat-chart=metrics]').evaluate("el=>echarts.getInstanceByDom(el).setOption({animation:false})")
    stats.locator('[data-stat-chart=registrations]').evaluate("el=>echarts.getInstanceByDom(el).setOption({animation:false})")
    assert '?' not in stats.inner_text() and 'NaN' not in stats.inner_text()
    page.screenshot(path='visual-baseline/verified/game-statistics-dialog.png')
    page.locator('[data-tab=first]').click()
    rect=dialog.bounding_box()
    assert abs(rect['width']-1536)<2 and abs(rect['height']-864)<2
    first.locator('[data-sort=lottery_price]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first th[aria-sort=descending]')!==null")
    first.locator('[data-sort=lottery_price]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first tbody td').textContent==='1'")
    first.locator('[data-page="2"]').first.click()
    page.wait_for_function("document.querySelector('#game-user-pane-first tbody td').textContent==='11'")
    page.locator('[data-tab=five]').click()
    five.locator('tbody tr').first.wait_for()
    assert five.locator('thead th').all_text_contents()==['Id','会员ID','用户账号','游戏名称','设备号','IP','登陆时间']
    assert five.locator('[data-sort=created_at]').locator('..').get_attribute('aria-sort')=='none'
    page.locator('[data-tab=first]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first tbody td').textContent==='11'")
    first.locator('[data-action=search]').click()
    first.locator('[name=username]').fill('user-11')
    first.locator('[type=submit]').click()
    page.wait_for_function("document.querySelectorAll('#game-user-pane-first tbody tr').length===1")
    assert first.locator('tbody td').first.inner_text()=='11'
    first.locator('[name=created_range]').fill('2025-02-30 00:00:00 - 2025-03-02 00:00:00')
    before=len(calls)
    first.locator('[type=submit]').click()
    assert first.locator('[role=alert]').inner_text()=='时间范围无效'
    assert len(calls)==before
    assert first.locator('[name=username]').input_value()=='user-11'
    first.locator('[name=created_range]').fill('2025-01-01 00:00:00 - 2025-01-02 00:00:00')
    first.locator('[type=submit]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first [role=alert]').textContent===''")
    page.wait_for_timeout(100)
    assert calls[-1][1]['created_from']=='2024-12-31T16:00:00.000Z'
    first.locator('[type=reset]').click()
    page.wait_for_function("document.querySelectorAll('#game-user-pane-first tbody tr').length===10")
    first.locator('[name=created_range]').focus()
    page.wait_for_selector('.game-user-dialog .daterangepicker:visible',state='visible')
    page.locator('[data-tab=five]').click()
    assert page.locator('.daterangepicker:visible').count()==0
    page.locator('[data-tab=first]').click()
    first.locator('.game-user-columns summary').click()
    first.locator('[data-column=trans_id]').uncheck()
    assert first.locator('thead th').count()==15
    first.locator('.game-user-columns summary').click()
    first.locator('[data-action=cards]').click()
    assert first.locator('.game-user-cards article').count()==10
    first.locator('[data-action=cards]').click()
    first.locator('[aria-label="每页记录数"]').click()
    first.locator('[data-game-size="15"]').click()
    page.wait_for_function("document.querySelectorAll('#game-user-pane-first tbody tr').length===15")
    count['value']=205
    first.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first .game-user-pagination').textContent.includes('205')")
    for export_type in ['json','xml','csv','txt','doc','excel']:
        first.locator('.game-user-export summary').click()
        with page.expect_download() as download:
            first.locator(f'[data-export={export_type}]').click()
        data=Path(download.value.path()).read_text(encoding='utf-8-sig')
        assert 'request-205' in data and 'request-1' in data
        assert 'trans-205' not in data
        if export_type=='json':
            assert len(json.loads(data)['data'])==205
    first.locator('[data-page="14"]:not([aria-label])').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first [aria-current=page]').textContent==='14'")
    count['value']=1
    first.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first [aria-current=page]').textContent==='1'")
    assert first.locator('tbody tr').count()==1
    count['fail']=True
    first.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first [role=alert]').textContent==='测试服务暂时不可用'")
    assert first.locator('tbody tr').count()==1
    first.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-first [role=alert]').textContent==='' && !document.querySelector('#game-user-pane-first .game-user-results').hasAttribute('aria-busy')")
    first.locator('[data-search-field=username]').click()
    assert first.locator('[name=username]').input_value()=='user-1'
    dialog.locator('[data-dialog-maximize]').click()
    assert page.evaluate("document.fonts.check('13px FontAwesome')")
    assert first.locator('[data-action=search] .shell-icon').inner_text()
    assert abs(dialog.bounding_box()['width']-1920)<2
    dialog.locator('[data-dialog-maximize]').click()
    page.screenshot(path='visual-baseline/verified/game-userdata-dialog.png')
    dialog.locator('[data-dialog-close]').click()
    dialog.wait_for(state='detached')
    assert page.evaluate('testStatCharts.every(chart=>chart.isDisposed())')
    page.wait_for_function("reviewDateBindings.size===0")
    assert page.locator('.daterangepicker').count()==0
    page.locator('[data-game-user]').first.click()
    first.locator('tbody tr').first.wait_for()
    assert first.locator('[name=username]').input_value()==''
    page.keyboard.press('Escape')
    dialog.wait_for(state='detached')
    dialog.wait_for(state='detached')
    page.locator('[data-game-user]').first.click()
    first.locator('tbody tr').first.wait_for()
    page.evaluate("location.hash='agents'")
    dialog.wait_for(state='detached')
    assert not errors, errors
    print('Game user-data dialog: scopes, tabs, filters, dates, paging, columns, cards, six exports and cleanup passed')
    browser.close()
