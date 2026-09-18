"""Exercise full exports, literal values, hidden fields and interrupted downloads."""
import csv
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright, expect

rows=[{'id':i+1,'parent_id':0,'user_id':i+10,'user_account':f'000{i:03}',
       'game_name':'Game <>&','agent_name':'Agent <>&','coin':999,'estimate_income':i/10,
       'is_fu':i%2,'fu_type':1,'is_look':1} for i in range(205)]
requests=[]
mode='normal'
pending=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080},accept_downloads=True)
    page.set_default_timeout(15000)
    def listing(route):
        query=parse_qs(urlparse(route.request.url).query)
        requests.append(query)
        assert route.request.headers.get('authorization','').startswith('Bearer ')
        offset=int(query['offset'][0]);limit=int(query['limit'][0])
        if mode=='delay' and limit==200:
            pending.append(route)
            return
        total=204 if mode=='changed' and offset==200 else len(rows)
        route.fulfill(json={'total':total,'items':rows[offset:offset+limit],'summary':{}})
    page.route('**/api/v1/ads?*',listing)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#adsExportToggle').wait_for()
    page.locator('#adsColumnsToggle').click()
    page.locator('[data-ads-column=agent_name]').check()
    page.locator('[data-ads-column=ecpm]').uncheck()
    page.locator('#adsColumnsToggle').click()
    page.fill('#adsFilters [name=user_id]','88')
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=submit]').click()
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-sort=estimate_income]').click()
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('[data-ads-page="2"]').first.click()
    expect(page.locator('#adsTable tbody tr').first.locator('[data-ads-field=id]')).to_have_text('11',use_inner_text=True)
    for kind in ['csv','json','xml','txt','doc','excel']:
        before=len(requests)
        page.locator('#adsExportToggle').click()
        with page.expect_download() as event:
            page.locator(f'[data-ads-export={kind}]').click()
        value=Path(event.value.path()).read_text(encoding='utf-8-sig')
        queries=requests[before:]
        assert [q['offset'][0] for q in queries]==['0','200']
        assert all(q['user_id']==['88'] and q['sort']==['estimate_income'] and q['order']==['desc'] for q in queries)
        assert 'ECPM' not in value and '代理商名称' in value
        if kind in ['csv','txt']:
            records=list(csv.reader(io.StringIO(value)))
            assert len(records)==206
            assert records[-1][records[0].index('用户账号')]=='000204'
            assert records[-1][records[0].index('金币')]=='20.4'
            assert records[-1][records[0].index('游戏名称')]=='Game <>&',records[-1]
        elif kind=='json':
            records=json.loads(value)['data']
            assert len(records)==205 and records[-1]['用户账号']=='000204'
            assert records[-1]['金币']==20.4 and records[-1]['代理商名称']=='Agent <>&'
        elif kind=='xml':
            root=ET.fromstring(value)
            assert len(root.findall('./data/row'))==205
            assert any(e.text=='Game <>&' for e in root.iter())
            assert len(root.findall('.//span'))==615
        else:
            assert '000000' in value and '000204' in value and value.count('<tbody>')==1
    downloads=[]
    page.on('download',lambda download:downloads.append(download))
    mode='changed'
    page.locator('#adsExportToggle').click()
    page.locator('[data-ads-export=csv]').click()
    expect(page.locator('#adsError')).to_have_text('数据已变化，请刷新后重新导出')
    expect(page.locator('#adsExportToggle')).to_be_enabled()
    assert not downloads
    mode='delay'
    page.locator('#adsExportToggle').click()
    page.locator('[data-ads-export=csv]').click()
    page.wait_for_timeout(100)
    expect(page.locator('#adsExportToggle')).to_be_disabled()
    page.evaluate("location.hash='dashboard'")
    page.locator('#adsTable').wait_for(state='detached')
    assert len(pending)==1
    pending.pop().fulfill(json={'total':0,'items':[],'summary':{}})
    page.wait_for_function('!adsState.exporting')
    assert not downloads
    assert page.locator('.review-export-table').count()==0
    browser.close()
print('PASS: 205-row six-format export, filters/sort, hidden columns, XML escaping, numeric account strings, changes and navigation cancellation')
