"""Check chart rendering and layout with deterministic, read-only fixtures."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/api/v1/games/*/statistics', lambda route: route.fulfill(json={
        'total_income': 123456.78, 'year_income': 456.78,
        'previous_month_income': 123, 'month_income': 45, 'yesterday_income': 12,
        'total_members': 1234, 'today_new': 12, 'today_login': 34,
        'update_date':'2026-09-18',
        'mapdata':[{'name':'北京','value':3,'coin':60,'rate':25},{'name':'浙江','value':9,'coin':180,'rate':75}],
        'mapdata1':['北京','浙江'],'mapdata2':[3,9],
        'metrics': [{'date': f'2026-09-{i:02d}', 'income': i*3, 'clicks': None,
                     'coin': i*4, 'activity': i*2} for i in range(1, 10)],
        'registrations': [{'date': f'2026-09-{i:02d}', 'count': i} for i in range(1, 10)],
    }))
    page.goto('http://127.0.0.1:3000/#games')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('form=>form.requestSubmit()')
    page.locator('[data-game-user]').first.click()
    page.locator('[data-tab=seven]').click()
    page.wait_for_function("document.querySelectorAll('[data-stat-chart] canvas').length===4")
    charts = page.locator('[data-stat-chart]')
    charts.evaluate_all("nodes=>nodes.forEach(node=>echarts.getInstanceByDom(node).setOption({animation:false}))")
    for width, height in [(1920, 1080), (1024, 768), (390, 844)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.wait_for_timeout(250)
        page.locator('.game-user-body').evaluate('el=>{el.scrollTop=0;}')
        assert page.locator('.game-user-stats').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
        assert page.locator('.game-stat-cards article').evaluate_all('nodes=>nodes.every(el=>el.scrollWidth<=el.clientWidth+1)')
        assert page.locator('.game-stat-cards strong').evaluate_all('nodes=>nodes.every(el=>el.offsetHeight<=parseFloat(getComputedStyle(el).lineHeight)+1)')
        if width==390:
            assert not page.locator('[data-stat-chart=region-map]').evaluate("el=>echarts.getInstanceByDom(el).getOption().series[0].label.show")
        assert charts.evaluate_all('''nodes=>nodes.every(el=>{
            const canvas=el.querySelector('canvas'),ctx=canvas.getContext('2d');
            return el.clientWidth>100 && Array.from(ctx.getImageData(0,0,canvas.width,canvas.height).data).some((v,i)=>i%4===3 && v>0);
        })''')
        assert page.locator('[data-stat-chart=region-map]').evaluate('''el=>{
            const canvas=el.querySelector('canvas'),pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
            let colored=0;
            for(let i=0;i<pixels.length;i+=4)if(pixels[i]>240&&pixels[i+1]>50&&pixels[i+1]<160&&pixels[i+2]<40&&pixels[i+3]>200)colored++;
            return colored>50;
        }''')
        page.screenshot(path=f'visual-baseline/verified/game-statistics-{width}.png')
        page.locator('[data-stat-chart=region-map]').scroll_into_view_if_needed()
        page.screenshot(path=f'visual-baseline/verified/game-statistics-map-{width}.png')
    assert page.locator('.game-stat-cards').inner_text().count('更新日期2026-09-18')==3
    assert page.locator('.game-stat-cards').inner_text().count('预估收益API')==5
    region=page.locator('[data-stat-chart=region-map]')
    assert region.evaluate("el=>echarts.getInstanceByDom(el).getOption().series[0].type")=='map'
    assert region.evaluate("el=>echarts.getInstanceByDom(el).getOption().visualMap[0].max")==9
    region.evaluate("el=>echarts.getInstanceByDom(el).dispatchAction({type:'mapSelect',name:'北京',seriesIndex:0})")
    assert region.evaluate("el=>echarts.getInstanceByDom(el).getModel().getSeriesByIndex(0).isSelected('北京')")
    region.evaluate("el=>echarts.getInstanceByDom(el).dispatchAction({type:'mapSelect',name:'浙江',seriesIndex:0})")
    assert not region.evaluate("el=>echarts.getInstanceByDom(el).getModel().getSeriesByIndex(0).isSelected('北京')")
    assert region.evaluate("el=>echarts.getInstanceByDom(el).getModel().getSeriesByIndex(0).isSelected('浙江')")
    region.evaluate("el=>echarts.getInstanceByDom(el).dispatchAction({type:'mapUnSelect',name:'浙江',seriesIndex:0})")
    assert not region.evaluate("el=>echarts.getInstanceByDom(el).getModel().getSeriesByIndex(0).isSelected('浙江')")
    page.set_viewport_size({'width':1920,'height':1080})
    page.wait_for_timeout(250)
    region.scroll_into_view_if_needed()
    point=region.evaluate("el=>echarts.getInstanceByDom(el).convertToPixel({seriesIndex:0},[120.153576,30.287459])")
    region.click(position={'x':point[0],'y':point[1]})
    assert region.evaluate("el=>echarts.getInstanceByDom(el).getModel().getSeriesByIndex(0).isSelected('浙江')")
    page.wait_for_function("document.querySelector('[data-stat-chart=region-map]').innerText.includes('账号数量 : 9个')")
    region.click(position={'x':point[0],'y':point[1]})
    assert not region.evaluate("el=>echarts.getInstanceByDom(el).getModel().getSeriesByIndex(0).isSelected('浙江')")
    metrics=page.locator('[data-stat-chart=metrics]')
    metrics.scroll_into_view_if_needed()
    width=metrics.evaluate('el=>el.clientWidth')
    metrics.click(position={'x':width-122,'y':15})
    metrics.locator('textarea').wait_for(state='visible')
    assert '预估收益API' in metrics.locator('textarea').input_value()
    metrics.get_by_text('关闭',exact=True).click()
    metrics.locator('textarea').wait_for(state='hidden')
    metrics.click(position={'x':width-68,'y':15})
    assert metrics.evaluate("el=>echarts.getInstanceByDom(el).getOption().series.every(series=>series.type==='bar')")
    metrics.click(position={'x':width-41,'y':15})
    assert metrics.evaluate("el=>echarts.getInstanceByDom(el).getOption().series.map(series=>series.type)")==['line','line','bar','bar']
    with page.expect_download() as download_info:
        metrics.click(position={'x':width-14,'y':15})
    download=download_info.value
    assert download.suggested_filename.endswith('.png')
    with open(download.path(),'rb') as exported:
        assert exported.read(8)==b'\x89PNG\r\n\x1a\n'
    assert page.locator('[data-stat-chart=region-bars]').evaluate("el=>echarts.getInstanceByDom(el).getOption().series[0].data")==[3,9]
    page.evaluate("()=>{window.savedGameCharts=Array.from(document.querySelectorAll('[data-stat-chart]'),el=>echarts.getInstanceByDom(el));}")
    page.locator('[data-tab=first]').click()
    assert page.evaluate('savedGameCharts.every(chart=>chart.isDisposed())')
    page.locator('[data-tab=seven]').click()
    page.wait_for_function("document.querySelectorAll('[data-stat-chart] canvas').length===4")
    page.evaluate("()=>{window.savedGameCharts=Array.from(document.querySelectorAll('[data-stat-chart]'),el=>echarts.getInstanceByDom(el));}")
    page.locator('[data-dialog-close]').click()
    page.locator('.game-user-dialog').wait_for(state='detached')
    assert page.evaluate('savedGameCharts.every(chart=>chart.isDisposed())')
    assert not errors, errors
    browser.close()
print('Statistics charts: responsive layout, map pixels/click/tooltip, data view, chart modes/restore, PNG export and cleanup passed')
