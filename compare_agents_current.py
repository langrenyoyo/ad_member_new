"""Agent list comparison using synthetic API permissions matching the reference account."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

OUT = Path('visual-baseline/fixtures/agents-current')
source = json.loads((OUT/'fixture-rows.json').read_text(encoding='utf-8'))
rows = [{**row, 'created_at': datetime.fromtimestamp(row['create_time'], timezone.utc).isoformat(),
    'updated_at': datetime.fromtimestamp(row['update_time'], timezone.utc).isoformat()} for row in source]
report = {}; mode = {'many': False}
with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
    def fixture(route):
        request = route.request; url = urlparse(request.url); path = url.path.removeprefix('/api/').removeprefix('v1/'); q = parse_qs(url.query)
        if path == 'auth/login': route.fulfill(json={'access_token': 'fixture', 'user': {'username': 'fixture'}}); return
        assert request.method == 'GET', request.url
        if path.endswith('/oss'):
            route.fulfill(json=dict(ossKey='synthetic-key',ossKeySecret='synthetic-secret',endPoint='https://fixture.invalid',bucket='fixture-bucket'));return
        items = [{**rows[i % 3], 'id': i+1} for i in range(225)] if mode['many'] else rows
        offset = int(q.get('offset', ['0'])[0]); limit = int(q.get('limit', ['10'])[0])
        route.fulfill(json={'items': items[offset:offset+limit], 'total': len(items), 'permissions': {'oss': True, 'dashboard': True, 'batch_status': False, 'edit': False, 'delete': False, 'create': False}} if path == 'agents' else {'items': [], 'total': 0})
    page.route('**/api/**', fixture)
    page.goto('http://127.0.0.1:3000/#agents')
    page.fill('#loginForm [name=username]', 'fixture'); page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#agentList tbody tr').first.wait_for(); page.evaluate('document.fonts.ready')
    assert page.locator('#reviewError').inner_text() == ''
    report['geometry'] = page.locator('#agentList th').evaluate_all('nodes=>nodes.map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width}))')
    report['styles'] = page.locator('#agentHost section,#agentList td,#agentList th,.agent-panel .ads-toolbar').evaluate_all('nodes=>nodes.slice(0,28).map(n=>{const c=getComputedStyle(n);return {tag:n.tagName,cls:n.className,height:n.getBoundingClientRect().height,font:c.font,padding:c.padding,align:c.textAlign,border:c.border}})')
    page.locator('#content').screenshot(path=str(OUT/'local.png'))
    page.locator('#agentSearchToggle').click(); page.locator('#content').screenshot(path=str(OUT/'filters-local.png'))
    page.locator('#agentSearchToggle').click()
    exports = []
    for prefix in ['', 'selected-']:
        if prefix:
            page.locator('[data-agent-select]').first.check()
            page.locator('#content').screenshot(path=str(OUT/'selection-local.png'))
        for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
            page.locator('.game-user-export summary').click()
            with page.expect_download() as download: page.locator('[data-export='+kind+']').click()
            download.value.save_as(str(OUT/(prefix+'export-local.'+kind)))
            values = {side: (OUT/(prefix+'export-'+side+'.'+kind)).read_text(encoding='utf-8-sig') for side in ['reference', 'local']}
            result = {'format': prefix+kind}
            if kind == 'json': values = {side: json.loads(value) for side, value in values.items()}
            if kind == 'xml':
                for side, value in list(values.items()):
                    try: values[side] = ET.tostring(ET.fromstring(value), encoding='unicode')
                    except ET.ParseError as error: result[side+'_parse_error'] = str(error)
            result['equal'] = values['reference'] == values['local']; exports.append(result)
        if prefix: page.locator('[data-agent-select]').first.uncheck()
    report['exports'] = exports
    page.locator('[data-action=cards]').click(); page.locator('#content').screenshot(path=str(OUT/'cards-local.png'))
    page.locator('[data-action=cards]').click(); mode['many'] = True; page.locator('#agentRefresh').click()
    page.wait_for_function('document.querySelector("#agentPagination").textContent.includes("225")')
    page.locator('#agentPagination').screenshot(path=str(OUT/'pagination-local.png'))
    mode['many'] = False; page.locator('#agentRefresh').click()
    page.wait_for_function('document.querySelector("#agentList tbody").rows.length===3')
    page.locator('[data-agent-oss]').first.click();page.locator('.agent-oss-dialog form').wait_for()
    page.locator('.agent-oss-dialog').screenshot(path=str(OUT/'oss-local.png'))
    assert not errors, errors; browser.close()
for mode in ['', 'filters-', 'selection-', 'cards-', 'pagination-', 'oss-']:
    reference = Image.open(OUT/(mode+'reference.png')).convert('RGB'); local = Image.open(OUT/(mode+'local.png')).convert('RGB')
    size = (max(reference.width, local.width), max(reference.height, local.height))
    a = Image.new('RGB', size, 'white'); a.paste(reference); b = Image.new('RGB', size, 'white'); b.paste(local)
    diff = ImageChops.difference(a, b); diff.save(OUT/(mode+'diff.png'))
    report[mode or 'table'] = {'reference_size': reference.size, 'local_size': local.size,
        'changed_pixels_percent': round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(size[0]*size[1])*100, 4)}
(OUT/'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key not in ['geometry','detail_styles','styles']}))
