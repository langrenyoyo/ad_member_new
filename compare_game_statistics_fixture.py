"""Compare four game charts using synthetic data; reference business requests are read-only."""
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

OUT = Path('visual-baseline/fixtures/game-statistics')
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
DATA = {
    'total_income': 123456.78, 'year_income': 456.78,
    'previous_month_income': 123, 'month_income': 45, 'yesterday_income': 12,
    'total_members': 1234, 'today_new': 12, 'today_login': 34,
    'update_date': '2026-09-18',
    'mapdata': [{'name': '北京', 'value': 3, 'coin': 60, 'rate': 25},
                {'name': '浙江', 'value': 9, 'coin': 180, 'rate': 75}],
    'mapdata1': ['北京', '浙江'], 'mapdata2': [3, 9],
    'metric_series': [{'date': f'2026-09-{i:02d}', 'income': i * 3,
                       'clicks': None, 'coin': i * 4, 'activity': i * 2} for i in range(1, 10)],
    'registration_series': [{'date': f'2026-09-{i:02d}', 'count': i} for i in range(1, 10)],
}

with sync_playwright() as p:
    browser = p.chromium.launch()
    ref = browser.new_page(viewport={'width': 1536, 'height': 822})
    ref.goto(BASE + '/index/login')
    ref.fill('[name=username]', '18532306918')
    ref.fill('[name=password]', '123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.wait_for_url(lambda url: '/index/login' not in url)
    result = ref.request.get(BASE + '/game/index', params={
        'limit': 1, 'offset': 0, 'filter': '{}', 'op': '{}',
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    game_id = result.json()['rows'][0]['id']

    def readonly(route):
        if route.request.method not in ('GET', 'HEAD') or any(
                part in route.request.url for part in ('imeiidban', 'deviceidban', '/del/', '/multi/')):
            route.abort()
        elif route.request.resource_type in ('xhr', 'fetch'):
            route.fulfill(json={'total': 0, 'rows': []})
        else:
            route.continue_()

    ref.route('**/*', readonly)
    ref.goto(BASE + f'/games/userdata/index/game_id/{game_id}', wait_until='networkidle')
    region_names = ref.evaluate('Config.mapdata.map(row=>row.name)')
    ref.evaluate('''data=>{
        Object.assign(Config,{column:data.registration_series.map(r=>r.date),
            userdata:data.registration_series.map(r=>r.count),
            column1:data.metric_series.map(r=>r.date),data1:data.metric_series.map(r=>r.income),
            data2:data.metric_series.map(r=>r.coin),data3:data.metric_series.map(r=>r.clicks),
            data4:data.metric_series.map(r=>r.activity),mapdata:data.mapdata,
            mapdata1:data.mapdata1,mapdata2:data.mapdata2});
        const pane=document.querySelector('#seven');
        const labels=['总金额（更新日期2026-09-18）','本年金额（更新日期2026-09-18）','上月金额','本月金额（更新日期2026-09-18）','昨日金额'];
        const money=['total_income','year_income','previous_month_income','month_income','yesterday_income'];
        pane.querySelectorAll('.panel-title h5').forEach((el,i)=>el.textContent=labels[i]);
        pane.querySelectorAll('h1').forEach((el,i)=>el.textContent='¥'+data[money[i]].toFixed(2));
        pane.querySelectorAll('.sm-st-info span').forEach((el,i)=>el.textContent=data[['total_members','today_new','today_login'][i]]);
    }''', DATA)
    ref.locator('.nav-tabs a[href="#seven"]').click()
    ref.wait_for_function("document.querySelectorAll('#seven canvas').length===4")
    ref.evaluate("()=>{window.fixtureEcharts=require('echarts');for(const id of ['echart1','echart3','echart4','echart'])fixtureEcharts.getInstanceByDom(document.getElementById(id)).setOption({animation:false});}")
    local = browser.new_page(viewport={'width': 1920, 'height': 1080})

    def fixture(route):
        if route.request.url.endswith('/auth/login'):
            route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}})
        elif route.request.url.endswith('/statistics'):
            route.fulfill(json=DATA)
        else:
            assert route.request.method == 'GET'
            route.fulfill(json={'total': 0, 'items': []})

    local.route('**/api/**', fixture)
    local.goto('http://127.0.0.1:3000/#games')
    local.fill('#loginForm [name=username]', 'fixture')
    local.fill('#loginForm [name=password]', 'fixture')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.locator('.app-shell').wait_for(state='visible')
    local.evaluate('openGameProfitData(42)')
    local.wait_for_function("document.querySelectorAll('[data-stat-chart] canvas').length===4")
    local.locator('[data-stat-chart]').evaluate_all('nodes=>nodes.forEach(el=>echarts.getInstanceByDom(el).setOption({animation:false}))')
    evidence = {'reference_region_names': region_names}
    for name, page, prefix in [('reference', ref, 'fixtureEcharts'), ('local', local, 'echarts')]:
        page.evaluate('document.fonts.ready')
        evidence[name] = page.evaluate('''([prefix,name])=>{
            const ids=name==='reference'?['#echart1','#echart3','#echart4','#echart']:['[data-stat-chart=metrics]','[data-stat-chart=region-map]','[data-stat-chart=region-bars]','[data-stat-chart=registrations]'];
            const engine=window[prefix];
            return {charts:ids.map(selector=>{const el=document.querySelector(selector),chart=engine.getInstanceByDom(el),o=chart.getOption();return {selector,rect:el.getBoundingClientRect().toJSON(),grid:o.grid,title:o.title,colors:o.color,mapStyle:o.series[0].itemStyle,theme:chart._theme};}),
                geometry:JSON.stringify(engine.getMap('china').geoJson),
                geometryShape:engine.getMap('china').geoJson.features.map(f=>({name:f.properties.name,cp:f.properties.cp,keys:Object.keys(f),geometryKeys:Object.keys(f.geometry)})),
                assets:performance.getEntriesByType('resource').map(r=>r.name).filter(n=>/china|echarts|theme/.test(n)),
                styles:(name==='reference'?['#seven','#seven>.row','.panel-body','.panel-title','.panel-title h5','.panel-content h1','.font-bold small','.sm-st','.sm-st-icon','.sm-st-info','.sm-st-info span','.st-violet','.st-green','.st-blue']:['.game-user-stats','.game-stat-cards','.game-stat-cards article','.game-stat-cards article>div','.game-stat-cards strong','.game-stat-cards article>span','.game-stat-counters article','.game-stat-counters i','.game-stat-counters article>div','.game-stat-counters strong']).map(selector=>{const el=document.querySelector(name==='reference'&&!selector.startsWith('#')?'#seven '+selector:selector),s=getComputedStyle(el);return {selector,rect:el.getBoundingClientRect().toJSON(),padding:s.padding,margin:s.margin,font:s.font,background:s.background,border:s.border,borderRadius:s.borderRadius};})};
        }''', [prefix, name])
    geometries = {name: json.loads(evidence[name].pop('geometry')) for name in ['reference', 'local']}
    evidence['same_geometry'] = geometries['reference'] == geometries['local']
    evidence['same_boundaries'] = {f['properties']['name']: f['geometry'] for f in geometries['reference']['features']} == {f['properties']['name']: f['geometry'] for f in geometries['local']['features']}
    evidence['boundary_differences'] = []
    for feature in geometries['reference']['features']:
        other = next(f for f in geometries['local']['features'] if f['properties']['name'] == feature['properties']['name'])
        changed = [key for key in feature['geometry'] if feature['geometry'][key] != other['geometry'].get(key)]
        if changed:
            evidence['boundary_differences'].append({'name': feature['properties']['name'], 'keys': changed})
    ref.wait_for_timeout(350)
    local.wait_for_timeout(350)
    ref.screenshot(path=str(OUT / 'top-reference.png'), animations='disabled')
    local.locator('.game-user-dialog main,.game-user-dialog>.game-user-body').screenshot(path=str(OUT / 'top-local.png'), animations='disabled')
    for key, ref_id in [('metrics', 'echart1'), ('region-map', 'echart3'), ('region-bars', 'echart4'), ('registrations', 'echart')]:
        ref.locator('#' + ref_id).screenshot(path=str(OUT / f'{key}-reference.png'), animations='disabled')
        local.locator(f'[data-stat-chart={key}]').screenshot(path=str(OUT / f'{key}-local.png'), animations='disabled')
    browser.close()

reports = {}
for key in ['top', 'metrics', 'region-map', 'region-bars', 'registrations']:
    a = Image.open(OUT / f'{key}-reference.png').convert('RGB')
    b = Image.open(OUT / f'{key}-local.png').convert('RGB')
    reports[key] = {'reference_size': a.size, 'local_size': b.size}
    if a.size == b.size:
        diff = ImageChops.difference(a, b)
        diff.save(OUT / f'{key}-diff.png')
        reports[key].update(changed_pixel_ratio=sum(max(pixel) > 10 for pixel in diff.get_flattened_data()) / (a.width * a.height),
                            mean_rgb=sum(ImageStat.Stat(diff).mean) / 3)
(OUT / 'measurements.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'report.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
print(json.dumps({'same_geometry': evidence['same_geometry'], 'charts': reports}, ensure_ascii=True))
