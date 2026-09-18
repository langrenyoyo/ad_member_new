"""Verify explicit agent routes never leak into global lists or lose scope on reload."""
from urllib.parse import urlparse, parse_qs
import csv
import io
import json
from pathlib import Path
from xml.etree import ElementTree
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('agent-dashboard-id','9000')")
    seen=[]
    def fixture(route):
        path=urlparse(route.request.url).path;query=parse_qs(urlparse(route.request.url).query)
        if path.endswith('/dashboard'):
            data={'agent_name':'主体甲','today_new':0,'today_login':0,'items':[]}
        elif path.endswith('/agents'):
            data={'total':2,'items':[{'id':9000,'name':'主体甲'},{'id':9001,'name':'主体乙'}]}
        elif path.endswith('/games'):
            data={'total':0,'items':[]}
        else:
            kind=path.rsplit('/',1)[-1];seen.append((kind,query))
            agent=int(query.get('agent_id',['0'])[0]);offset=int(query.get('offset',['0'])[0])
            rows=[{'id':100+i,'username':f'scope-{agent}-{i}','agent_id':agent,'name':'对照会员','good_name':'商品 & <测试>','game_id':1,'status':1,'vip':0,'created_at':'2026-09-17T00:00:00Z'} for i in range(25)]
            data={'total':25,'items':rows[offset:offset+int(query.get('limit',['20'])[0])]}
        route.fulfill(json=data)
    for pattern in ['**/api/v1/agents/*/dashboard','**/api/v1/agents?*','**/api/v1/games?*','**/api/v1/members?*','**/api/v1/withdrawals?*']:
        page.route(pattern,fixture)
    page.goto('http://127.0.0.1:3000/#agent-dashboard')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.agent-dashboard-tools a[href="#members?agent_id=9000"]').click()
    page.get_by_text('scope-9000-0',exact=False).first.wait_for()
    assert seen[-1][1]['agent_id']==['9000']
    for selector in ['#nextPage','#memberFilterReset','#refresh']:
        with page.expect_response(lambda r:'/api/v1/members?' in r.url):page.locator(selector).click()
        assert seen[-1][1]['agent_id']==['9000']
    page.reload();page.locator('.member-filters').wait_for()
    assert seen[-1][1]['agent_id']==['9000']
    page.locator('#nav a[href="#members"]').click()
    page.get_by_text('scope-0-0',exact=False).first.wait_for()
    assert 'agent_id' not in seen[-1][1]
    page.locator('.target-tabs a[href="#members?agent_id=9000"]').click()
    page.get_by_text('scope-9000-0',exact=False).first.wait_for()
    assert seen[-1][1]['agent_id']==['9000']
    page.evaluate("location.hash='agent-dashboard'")
    page.locator('.agent-dashboard-tools a[href="#withdrawals?agent_id=9000"]').click()
    page.get_by_text('scope-9000-0',exact=True).wait_for()
    assert seen[-1][1]['agent_id']==['9000']
    assert page.locator('#reviewFilters [name=agent_id]').is_disabled()
    output=Path('visual-baseline/fixtures/withdrawals-export');output.mkdir(parents=True,exist_ok=True)
    page.locator('.review-export summary').click()
    with page.expect_download() as event:page.locator('[data-review-export=csv]').click()
    csv_text=Path(event.value.path()).read_text(encoding='utf-8-sig')
    csv_rows=list(csv.reader(io.StringIO(csv_text)))
    assert len(csv_rows)==26 and 'scope-9000-24' in csv_text
    assert 'scope-9001-' not in csv_text and 'scope-0-' not in csv_text
    assert seen[-1][1]['agent_id']==['9000'] and seen[-1][1]['limit']==['200']
    (output/'export.csv').write_text(csv_text,encoding='utf-8-sig')
    page.locator('[data-withdrawal-select="100"]').check()
    request_count=len(seen)
    page.locator('.review-export summary').click()
    with page.expect_download() as event:page.locator('[data-review-export=xml]').click()
    xml_text=Path(event.value.path()).read_text(encoding='utf-8-sig')
    parsed=ElementTree.fromstring(xml_text)
    assert len(parsed.findall('./data/row'))==1
    assert any(node.text=='商品 & <测试>' for node in parsed.findall('./data/row/*'))
    assert len(seen)==request_count
    (output/'selected.xml').write_text(xml_text,encoding='utf-8')
    page.locator('[data-withdrawal-select="100"]').uncheck()
    (output/'report.json').write_text(json.dumps({'scope':'browser-only scoped withdrawals; no business writes','agent_id':9000,'csv_records':25,'selected_xml_records':1,'special_character_roundtrip':True},indent=2),encoding='utf-8')
    page.locator('#reviewFilters [name=agent_id]').evaluate("el=>{el.disabled=false;el.value='9001';}")
    with page.expect_response(lambda r:'/api/v1/withdrawals?' in r.url):
        page.locator('#reviewFilters [type=submit]').click()
    assert seen[-1][1]['agent_id']==['9000']
    for selector in ['#reviewFilters [type=reset]','[data-review-status="1"]','#reviewRefresh']:
        with page.expect_response(lambda r:'/api/v1/withdrawals?' in r.url):page.locator(selector).click()
        assert seen[-1][1]['agent_id']==['9000']
    page.reload();page.locator('#reviewFilters').wait_for()
    assert seen[-1][1]['agent_id']==['9000']
    page.locator('#nav a[href="#withdrawals"]').click()
    page.get_by_text('scope-0-0',exact=True).wait_for()
    assert 'agent_id' not in seen[-1][1]
    assert page.locator('#reviewFilters [name=agent_id]').is_enabled()
    page.evaluate("location.hash='withdrawals?agent_id=9001'")
    page.get_by_text('scope-9001-0',exact=True).wait_for()
    assert seen[-1][1]['agent_id']==['9001']
    assert page.locator('#reviewFilters [name=agent_id]').input_value()=='9001'
    assert not errors,errors
    browser.close()
print('Explicit agent members/withdrawals: scoped entry, reset, paging, status, refresh, reload, tabs, global exit and agent switch passed')
