"""Validate all six real downloads with paginated synthetic records."""
import csv
import io
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright

rows=[dict(id=i,name=f'主体-{i:03d} 中文 & <测试> "引号"',status=i%2,parent_id=0,created_at='2026-09-16T00:00:00Z') for i in range(1,206)]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();requests=[]
    def respond(route):
        q=parse_qs(urlparse(route.request.url).query);requests.append(q)
        offset=int(q.get('offset',[0])[0]);limit=int(q.get('limit',[10])[0])
        route.fulfill(json={'total':len(rows),'items':rows[offset:offset+limit]})
    page.route('**/api/v1/agents?*',respond)
    page.goto('http://127.0.0.1:3000/#agents')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-agent-select]').first.wait_for()
    for kind in ['csv','json','xml','txt','doc','excel']:
        page.locator('.agent-export summary').click()
        with page.expect_download() as event:page.locator(f'[data-agent-export={kind}]').click()
        content=Path(event.value.path()).read_text(encoding='utf-8-sig')
        assert '主体-205' in content,kind
        assert '主体-001' in content,kind
        if kind=='csv':
            data=list(csv.reader(io.StringIO(content)));assert len(data)==206
            assert data[1][1]==rows[0]['name']
        elif kind=='json':
            data=json.loads(content);assert len(data['data'])==205,kind
        elif kind=='xml':
            Path('visual-baseline/fixtures/agents/export.xml').write_text(content,encoding='utf-8')
            ET.fromstring(content)
            parsed=ET.fromstring(content)
            assert len(parsed.findall('./data/row'))==205
            assert parsed.find('./data/row/column-2').text==rows[0]['name']
        elif kind in ['doc','excel']:
            assert '<table' in content.lower() or '<worksheet' in content.lower(),kind
        assert any(q.get('offset')==['200'] for q in requests)
        assert page.locator('#reviewError').inner_text()==''
        print(kind,'download content passed')
    browser.close()
