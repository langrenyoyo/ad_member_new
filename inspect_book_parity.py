"""Read-only tutorial inspection with synthetic list and detail responses."""
import ast
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
OUT = Path('visual-baseline/fixtures/book'); OUT.mkdir(parents=True, exist_ok=True)
source = ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))
credentials = {}
rows = [{'id': 3-i, 'name': ['Fixture tutorial', 'Fixture <>&', 'Fixture longer tutorial'][i], 'create_time': 1789689600+i*60, 'update_time': 1789776000+i*60} for i in range(3)]
(OUT/'fixture-rows.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
for node in ast.walk(source):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'fill' and len(node.args) == 2:
        key = ast.literal_eval(node.args[0])
        if key in ('[name=username]', '[name=password]'): credentials[key] = ast.literal_eval(node.args[1])

with sync_playwright() as p:
    browser = p.chromium.launch(); page = browser.new_page(viewport={'width': 1690, 'height': 1030})
    page.goto(BASE+'/index/login')
    for selector, value in credentials.items(): page.fill(selector, value)
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_url(lambda url: '/index/login' not in url)
    requests = []; mode = {'many': False}
    def readonly(route):
        request = route.request; url = urlparse(request.url)
        if request.method not in ('GET', 'HEAD') or any(part in url.path for part in ('/update', '/lahei', '/multi', '/del', '/agree', '/refuse', '/alipay', '/ban', '/coinclear')):
            route.abort(); return
        if '/book' in url.path and request.headers.get('x-requested-with') == 'XMLHttpRequest':
            q = parse_qs(url.query); requests.append(q)
            items = [{**rows[i % 3], 'id': i+1} for i in range(225)] if mode['many'] else rows
            start = int(q.get('offset', ['0'])[0]); limit = int(q.get('limit', [str(len(items))])[0])
            route.fulfill(json={'total': len(items), 'rows': items[start:start+limit]}); return
        if url.hostname == 'api.xmchujian.com': route.abort(); return
        route.continue_()
    page.route('**/*', readonly)
    page.wait_for_load_state('networkidle')
    actual = page.request.get(BASE+'/book/index', params={'sort': 'id', 'order': 'desc', 'limit': 200, 'offset': 0}, headers={'X-Requested-With': 'XMLHttpRequest'}).json()
    local = json.loads(Path('public/target-book.json').read_text(encoding='utf-8-sig'))
    snapshot = {'reference_count': actual.get('total'), 'local_count': len(local['rows']),
        'rows_equal': actual.get('rows') == local['rows']}
    links = page.locator('a').evaluate_all("nodes=>nodes.filter(n=>n.textContent.includes('教程')).map(n=>({text:n.textContent.trim(),href:n.getAttribute('href'),url:n.dataset.url}))")
    page.goto(BASE+'/book', wait_until='networkidle')
    page.wait_for_function("window.jQuery&&jQuery('#table').data('bootstrap.table')&&jQuery.active===0")
    response = page.request.get('https://ad.leadink.cn/assets/js/backend/book.js')
    if response.ok: (OUT/'reference-controller.js').write_text(response.text(), encoding='utf-8')
    report = page.evaluate("""()=>{const o=jQuery('#table').bootstrapTable('getOptions');return {
      table:{sortName:o.sortName,sortOrder:o.sortOrder,pageSize:o.pageSize,pageList:o.pageList,search:o.search,showToggle:o.showToggle,showColumns:o.showColumns,showExport:o.showExport,showRefresh:o.showRefresh,commonSearch:o.commonSearch,
        columns:o.columns.map(cols=>cols.map(c=>({field:c.field,title:c.title,visible:c.visible,sortable:c.sortable,operate:c.operate,formatter:c.formatter?.toString()})))},
      controls:[...document.querySelectorAll('button,a.btn')].map(n=>({text:n.textContent,cls:n.className,href:n.getAttribute('href'),title:n.title})),
      geometry:[...document.querySelectorAll('#table th')].map(n=>({field:n.dataset.field,width:n.getBoundingClientRect().width})),
      cells:[...document.querySelectorAll('#table tbody tr:first-child td')].map(n=>({text:n.textContent,html:n.innerHTML}))
    }}""")
    page.evaluate('document.fonts.ready'); page.locator('#main').screenshot(path=str(OUT/'reference.png'))
    page.locator('[name=commonSearch]').click(); page.locator('#main').screenshot(path=str(OUT/'filters-reference.png'))
    report['filters'] = page.locator('.commonsearch-table input').evaluate_all('nodes=>nodes.map(n=>({name:n.name,placeholder:n.placeholder,type:n.type}))')
    page.locator('[name=commonSearch]').click()
    for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
        page.locator('.export button').click()
        with page.expect_download() as download: page.locator('.export [data-type="'+kind+'"]').click()
        download.value.save_as(str(OUT/('export-reference.'+kind)))
    page.locator('[name=btSelectItem]').first.check()
    page.locator('#main').screenshot(path=str(OUT/'selection-reference.png'))
    for kind in ['json', 'xml', 'csv', 'txt', 'doc', 'excel']:
        page.locator('.export button').click()
        with page.expect_download() as download: page.locator('.export [data-type="'+kind+'"]').click()
        download.value.save_as(str(OUT/('selected-export-reference.'+kind)))
    page.locator('[name=btSelectItem]').first.uncheck()
    page.locator('[name=toggle]').click(); page.locator('#main').screenshot(path=str(OUT/'cards-reference.png'))
    page.locator('[name=toggle]').click(); mode['many'] = True; page.locator('.btn-refresh').click()
    page.wait_for_function('jQuery.active===0'); page.locator('.fixed-table-pagination').screenshot(path=str(OUT/'pagination-reference.png'))
    mode['many'] = False; page.locator('.btn-refresh').click(); page.wait_for_function('jQuery.active===0')
    report['links'] = links; report['requests'] = requests; report['source_snapshot'] = snapshot
    (OUT/'reference.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    page.locator('#table tbody a').first.click()
    page.wait_for_timeout(1000)
    report['frames'] = [{'url': f.url, 'structure': f.locator('body>*').evaluate_all('nodes=>nodes.map(n=>({tag:n.tagName,id:n.id,cls:n.className}))')} for f in page.frames]
    frame = next(f for f in page.frames if '/book/detail/' in f.url)
    report['detail_structure'] = frame.locator('#main,#main *').evaluate_all("""nodes=>nodes.slice(0,25).map(n=>{const c=getComputedStyle(n),r=n.getBoundingClientRect();return {tag:n.tagName,id:n.id,cls:n.className,children:n.children.length,x:r.x,y:r.y,width:r.width,height:r.height,font:c.font,padding:c.padding,margin:c.margin,border:c.border}})""")
    report['window'] = page.locator('.layui-layer').evaluate('n=>({x:n.offsetLeft,y:n.offsetTop,width:n.offsetWidth,height:n.offsetHeight,html:n.querySelector(".layui-layer-title")?.outerHTML,buttons:n.querySelector(".layui-layer-setwin")?.innerHTML})')
    content = '<p style="text-align:center;font-size:24px">Fixture tutorial</p><p>Fixture &lt;&gt;&amp; content</p><p><strong>Bold fixture</strong> <em>Italic fixture</em></p><p><img src="/assets/img/avatar.png" width="100" height="100" alt="Fixture image"></p><p><a href="https://example.com/">Fixture link</a></p>'
    (OUT/'fixture-content.html').write_text(content, encoding='utf-8')
    frame.locator('#edit-form .form-group').evaluate('(n,html)=>n.innerHTML=html', content)
    frame.wait_for_function('[...document.images].every(n=>n.complete&&n.naturalWidth>0)')
    page.locator('.layui-layer').screenshot(path=str(OUT/'detail-reference.png'))
    report['detail_styles'] = frame.locator('body,.content,#edit-form,.form-group,.form-group p,.form-group a').evaluate_all('nodes=>nodes.map(n=>{const c=getComputedStyle(n),r=n.getBoundingClientRect();return {tag:n.tagName,cls:n.className,background:c.backgroundColor,font:c.font,color:c.color,smoothing:c.webkitFontSmoothing,rendering:c.textRendering,weight:c.fontWeight,x:r.x,y:r.y,width:r.width,height:r.height}})')
    page.locator('#table tbody a').nth(1).click(); page.wait_for_timeout(1200)
    report['simultaneous_windows'] = page.locator('.layui-layer').count()
    report['window_stack'] = page.locator('.layui-layer').evaluate_all('nodes=>nodes.map(n=>({id:n.id,cls:n.className,display:getComputedStyle(n).display,visibility:getComputedStyle(n).visibility,width:n.offsetWidth,height:n.offsetHeight,minDisplay:getComputedStyle(n.querySelector(".layui-layer-min")).display}))')
    page.keyboard.press('Escape'); page.wait_for_timeout(500)
    report['windows_after_escape'] = page.locator('.layui-layer').count()
    page.locator('.layui-layer').last.locator('.layui-layer-min').click()
    report['minimized_windows'] = page.locator('.layui-layer').evaluate_all('nodes=>nodes.map(n=>({left:n.offsetLeft,top:n.offsetTop,width:n.offsetWidth,height:n.offsetHeight,display:getComputedStyle(n).display,minDisplay:getComputedStyle(n.querySelector(".layui-layer-min")).display}))')
    page.locator('#table tbody a').nth(1).click(); page.wait_for_timeout(1200)
    page.locator('.layui-layer').last.locator('.layui-layer-min').click()
    report['two_minimized'] = page.locator('.layui-layer').evaluate_all('nodes=>nodes.map(n=>({left:n.offsetLeft,top:n.offsetTop,width:n.offsetWidth,height:n.offsetHeight}))')
    page.locator('.layui-layer').last.locator('.layui-layer-close').click(); page.wait_for_timeout(400)
    report['restored_stack'] = page.locator('.layui-layer').evaluate_all('nodes=>nodes.map(n=>({id:n.id,display:getComputedStyle(n).display,width:n.offsetWidth,height:n.offsetHeight}))')
    (OUT/'reference.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['window_stack','windows_after_escape','minimized_windows','two_minimized','restored_stack']}, ensure_ascii=False))
    browser.close()
