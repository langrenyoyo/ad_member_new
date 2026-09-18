"""Read-only tutorial fixture comparison, including selected exports and rich text."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

OUT = Path('visual-baseline/fixtures/book')
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
        if path.startswith('tutorials/'):
            route.fulfill(json={**rows[0], 'content': (OUT/'fixture-content.html').read_text(encoding='utf-8')}); return
        items = [{**rows[i % 3], 'id': i+1} for i in range(225)] if mode['many'] else rows
        offset = int(q.get('offset', ['0'])[0]); limit = int(q.get('limit', ['10'])[0])
        route.fulfill(json={'items': items[offset:offset+limit], 'total': len(items)} if path == 'tutorials' else {'items': [], 'total': 0})
    page.route('**/api/**', fixture)
    page.goto('http://127.0.0.1:3000/#book')
    page.fill('#loginForm [name=username]', 'fixture'); page.fill('#loginForm [name=password]', 'fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('#tutorialList tbody tr').first.wait_for(); page.evaluate('document.fonts.ready')
    assert page.locator('#tutorialError').inner_text() == ''
    report['geometry'] = page.locator('#tutorialList th').evaluate_all('nodes=>nodes.map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width}))')
    page.locator('#content').screenshot(path=str(OUT/'local.png'))
    page.locator('#tutorialSearch').click(); page.locator('#content').screenshot(path=str(OUT/'filters-local.png'))
    page.locator('#tutorialSearch').click()
    exports = []
    for prefix in ['', 'selected-']:
        if prefix:
            page.locator('[data-tutorial-select]').first.check()
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
        if prefix: page.locator('[data-tutorial-select]').first.uncheck()
    report['exports'] = exports
    page.locator('[data-action=cards]').click(); page.locator('#content').screenshot(path=str(OUT/'cards-local.png'))
    page.locator('[data-action=cards]').click(); mode['many'] = True; page.locator('#tutorialRefresh').click()
    page.wait_for_function('document.querySelector("#tutorialPagination").textContent.includes("225")')
    page.locator('#tutorialPagination').screenshot(path=str(OUT/'pagination-local.png'))
    mode['many'] = False; page.locator('#tutorialRefresh').click()
    page.wait_for_function('document.querySelector("#tutorialList tbody").rows.length===3')
    page.locator('[data-tutorial]').first.click(); page.frame_locator('.tutorial-frame').locator('.tutorial-content').wait_for()
    frame = page.locator('.tutorial-frame').element_handle().content_frame()
    frame.wait_for_function('[...document.images].every(n=>n.complete&&n.naturalWidth>0)')
    page.locator('.tutorial-dialog').screenshot(path=str(OUT/'detail-local.png'))
    report['detail_styles'] = frame.locator('.tutorial-content,.tutorial-content p,.tutorial-content a').evaluate_all('nodes=>nodes.map(n=>{const c=getComputedStyle(n),r=n.getBoundingClientRect();return {tag:n.tagName,cls:n.className,background:c.backgroundColor,font:c.font,color:c.color,smoothing:c.webkitFontSmoothing,rendering:c.textRendering,weight:c.fontWeight,x:r.x,y:r.y,width:r.width,height:r.height}})')
    assert not errors, errors; browser.close()
for mode in ['', 'filters-', 'selection-', 'cards-', 'pagination-', 'detail-']:
    reference = Image.open(OUT/(mode+'reference.png')).convert('RGB'); local = Image.open(OUT/(mode+'local.png')).convert('RGB')
    size = (max(reference.width, local.width), max(reference.height, local.height))
    a = Image.new('RGB', size, 'white'); a.paste(reference); b = Image.new('RGB', size, 'white'); b.paste(local)
    diff = ImageChops.difference(a, b); diff.save(OUT/(mode+'diff.png'))
    report[mode or 'table'] = {'reference_size': reference.size, 'local_size': local.size,
        'changed_pixels_percent': round(sum(max(pixel)>16 for pixel in diff.get_flattened_data())/(size[0]*size[1])*100, 4)}
(OUT/'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key not in ['geometry','detail_styles']}))
