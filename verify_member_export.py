"""Member export real downloads with isolated API fixtures."""
import csv,io,json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright

rows=[{'id':i,'username':f'会员-{i:03d} & <测试> "引号"','receive_name':'收款姓名','coin':12.5,'status':1,'vip':0,'created_at':'2026-09-16T00:00:00Z'} for i in range(1,206)]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});requests=[];downloads=[];held=[];hold=False;changed=False
    def respond(route):
        q=parse_qs(urlparse(route.request.url).query);requests.append(q)
        if hold and q.get('limit')==['200']:held.append(route);return
        offset=int(q['offset'][0]);limit=int(q['limit'][0])
        route.fulfill(json={'total':204 if changed and offset==200 else len(rows),'items':rows[offset:offset+limit]})
    page.route('**/api/v1/members?*',respond);page.on('download',lambda item:downloads.append(item))
    page.goto('http://127.0.0.1:3000/#members?agent_id=9000')
    page.fill('#loginForm [name=username]','18532306918');page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-export').wait_for()
    page.fill('[data-mf=username]','会员');page.locator('#memberFilterSubmit').click()
    page.wait_for_function("!document.querySelector('#content').hasAttribute('aria-busy')")
    page.locator('.member-columns summary').click();page.locator('[data-member-column=created_at]').uncheck()
    page.locator('.member-columns summary').focus();page.keyboard.press('Escape')
    def download(kind):
        page.locator('.member-export summary').click()
        with page.expect_download() as event:page.locator(f'[data-member-export={kind}]').click()
        return Path(event.value.path()).read_text(encoding='utf-8-sig')
    content=download('csv');data=list(csv.reader(io.StringIO(content)))
    assert len(data)==206 and data[1][1]==rows[0]['username'] and data[-1][0]=='205'
    assert '操作' not in data[0] and '创建时间' not in data[0]
    assert all(q.get('agent_id')==['9000'] and q.get('username')==['会员'] for q in requests if q.get('limit')==['200'])
    assert any(q['offset']==['200'] for q in requests)
    page.locator('[data-select="1"]').check();page.locator('#memberViewToggle').click()
    before=len(requests)
    for kind in ['csv','json','xml','txt','doc','excel']:
        content=download(kind)
        assert '会员-001' in content and '会员-002' not in content
        if kind=='xml':
            root=ET.fromstring(content);assert len(root.findall('./data/row'))==1
            assert root.find('./data/row/column-2').text==rows[0]['username']
        if kind=='json':assert len(json.loads(content)['data'])==1
        assert page.locator('.member-export-error').inner_text()==''
    assert len(requests)==before
    page.locator('[data-select="1"]').uncheck();changed=True;count=len(downloads)
    page.locator('.member-export summary').click();page.locator('[data-member-export=csv]').click()
    page.get_by_text('数据已变化，请刷新后重新导出',exact=True).wait_for()
    assert len(downloads)==count
    changed=False;hold=True
    page.locator('.member-export summary').click();page.locator('[data-member-export=csv]').click()
    page.wait_for_function("document.querySelector('.member-export').getAttribute('aria-busy')==='true'")
    # Flush the request handler before navigating away.
    page.wait_for_timeout(100)
    assert held
    count=len(downloads);page.evaluate("location.hash='agents'");page.locator('.agent-panel').wait_for()
    held[0].fulfill(json={'total':1,'items':rows[:1]})
    page.wait_for_load_state('networkidle')
    assert len(downloads)==count and page.locator('[data-member-toolbar]').count()==0
    browser.close()
print('Member export: 205 filtered/scoped CSV rows, selected six formats in cards, XML escaping, hidden columns and navigation cancellation passed')
