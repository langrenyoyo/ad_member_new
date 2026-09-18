from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3010/')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.goto('http://127.0.0.1:3010/#agents',wait_until='networkidle')
    page.locator('.agent-panel').wait_for()
    assert page.locator('.agent-panel').count()==1
    assert page.locator('#agentFilters').is_hidden()
    page.locator('#agentSearchToggle').click()
    page.fill('#agentFilters [name=name]','nonexistent-agent-fixture')
    with page.expect_response(lambda r:'/api/v1/agents?' in r.url and 'name=nonexistent' in r.url) as response:
        page.locator('#agentFilters [type=submit]').click()
    assert response.value.status==200 and response.value.json()['total']==0
    page.wait_for_function("document.querySelector('#agentSelectAll').disabled")
    assert page.locator('#agentFilters [name=name]').input_value()=='nonexistent-agent-fixture'
    page.locator('#agentFilters [type=reset]').click()
    page.wait_for_function("document.querySelector('#agentFilters [name=name]').value==='' && !document.querySelector('#agentSelectAll').disabled")
    page.locator('#agentSelectAll').check()
    assert all(page.locator('[data-agent-select]').evaluate_all('(els)=>els.map(e=>e.checked)'))
    with page.expect_response(lambda r:'/api/v1/agents?' in r.url and 'sort=created_at' in r.url) as response:
        page.locator('[data-agent-sort=created_at]').click()
    assert response.value.status==200
    page.wait_for_function("document.querySelector('[data-agent-sort=created_at]').textContent.includes('▼')")
    page.screenshot(path='visual-baseline/verified/agents-list.png',full_page=True)
    saved=[]
    def oss_route(route):
        if route.request.method=='PATCH':
            saved.append(route.request.post_data_json)
            route.fulfill(json={'saved':True})
        else:
            route.fulfill(json={'ossKey':'fixture-key','ossKeySecret':'fixture-secret','endPoint':'fixture-endpoint','bucket':'fixture-bucket'})
    page.route('**/api/v1/agents/*/oss',oss_route)
    page.locator('[data-agent-oss]').first.click()
    page.locator('.agent-oss-dialog [name=bucket]').fill('changed')
    page.locator('.agent-oss-dialog [type=reset]').click()
    assert page.locator('.agent-oss-dialog [name=bucket]').input_value()=='fixture-bucket'
    page.locator('.agent-oss-dialog [name=bucket]').fill('changed')
    page.locator('.agent-oss-dialog [type=submit]').click()
    page.locator('.agent-oss-dialog').wait_for(state='detached')
    assert saved==[{'ossKey':'fixture-key','ossKeySecret':'fixture-secret','endPoint':'fixture-endpoint','bucket':'changed'}]
    page.locator('[data-agent-enter]').first.click()
    page.locator('.agent-dashboard-chart').wait_for()
    assert page.locator('.agent-dashboard-cards article').count()==2
    page.wait_for_function("window.echarts?.getInstanceByDom(document.querySelector('#agentChart'))?.getOption().series[0].data.length===31")
    assert page.evaluate("echarts.getInstanceByDom(document.querySelector('#agentChart')).getOption().series[0].smooth")
    page.evaluate("echarts.getInstanceByDom(document.querySelector('#agentChart')).dispatchAction({type:'showTip',seriesIndex:0,dataIndex:15})")
    page.wait_for_function("document.querySelector('#agentChart').textContent.includes('注册用户数')")
    page.evaluate("echarts.getInstanceByDom(document.querySelector('#agentChart')).dispatchAction({type:'legendToggleSelect',name:'注册用户数'})")
    assert page.evaluate("echarts.getInstanceByDom(document.querySelector('#agentChart')).getOption().legend[0].selected['注册用户数']===false")
    page.reload(wait_until='networkidle')
    page.locator('.agent-dashboard-chart').wait_for()
    page.wait_for_function("agentCharts.size===1")
    page.locator('.agent-dashboard-tools a[href="#agent-games"]').click()
    page.locator('#agentGameFilters').wait_for()
    page.fill('#agentGameFilters [name=game_key]','fixture%key')
    page.select_option('#agentGameFilters [name=is_landscape]','1')
    page.select_option('#agentGameFilters [name=ad_status]','0')
    page.fill('#agentGameFilters [name=name]','nonexistent-scope-game')
    with page.expect_response(lambda r:'/api/v1/games?' in r.url and 'name=nonexistent' in r.url) as response:
        page.locator('#agentGameFilters [type=submit]').click()
    assert response.value.status==200 and response.value.json()['total']==0
    assert 'agent_id=' in response.value.url
    assert 'game_key=fixture%25key' in response.value.url and 'ad_status=0' in response.value.url
    page.fill('#agentGameFilters [name=created_range]','invalid')
    page.locator('.daterangepicker:visible').wait_for()
    page.locator('#agentGameFilters [name=created_range]').press('Escape')
    page.locator('#agentGameFilters [type=submit]').click()
    assert page.locator('#agentGameFilters [name=created_range]').input_value()=='invalid'
    assert page.locator('#agentGameError').inner_text()
    page.locator('#agentGameFilters [type=reset]').click()
    page.wait_for_function("document.querySelector('#agentGameFilters [name=game_key]').value===''")
    page.locator('.agent-dashboard-tools a[href="#agent-dashboard"]').click()
    page.wait_for_function('agentCharts.size===1')
    page.set_viewport_size({'width':1400,'height':900})
    page.wait_for_function("Math.abs(echarts.getInstanceByDom(document.querySelector('#agentChart')).getWidth()-document.querySelector('#agentChart').clientWidth)<2")
    page.goto('http://127.0.0.1:3010/#agents',wait_until='networkidle')
    page.wait_for_function('agentCharts.size===0')
    assert not errors,errors
    browser.close()
    print('PASS agents route, name/reset, selection and date sort; no business mutations.')
