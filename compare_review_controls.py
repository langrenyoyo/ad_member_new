"""Compare review controls with browser fixtures; block reference business writes."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright, expect

out = Path('visual-baseline/fixtures/review-controls')
out.mkdir(parents=True, exist_ok=True)
results = {}
with sync_playwright() as p:
    browser = p.chromium.launch()
    ref = browser.new_page(viewport={'width': 1690, 'height': 1030})
    local = browser.new_page(viewport={'width': 1920, 'height': 1080})
    fixtures = {kind: json.loads(Path(f'visual-baseline/fixtures/{kind}/data.json').read_text(encoding='utf-8')) for kind in ('withdrawals', 'subsidies')}
    def handle(route):
        req = route.request
        path = urlparse(req.url).path
        for remote, kind in [('tixian', 'withdrawals'), ('butie', 'subsidies')]:
            if path.endswith('/' + remote + '/index') and req.resource_type in ('xhr', 'fetch'):
                return route.fulfill(json={'total': 3, 'rows': fixtures[kind]['reference'], 'extend': {'tixian1': 123.4, 'tixian2': 0, 'tixian3':25}})
        if 'List_source' in path:
            rows = [{'id': 7200 + i, 'name': f'Game {i:02d}'} for i in range(12)]
            return route.fulfill(json={'total': 12, 'list': rows[:10]})
        if (req.method not in ('GET', 'HEAD') and not path.endswith('/index/login')) or any(part in path for part in ('/lahei','/agree','/refuse','/alipay','/del','/multi')):
            return route.abort()
        route.continue_()
    ref.route('**/*', handle)
    def listing(route):
        kind = urlparse(route.request.url).path.rsplit('/', 1)[-1]
        route.fulfill(json={'total': 3, 'items': fixtures[kind]['local'], 'summary': {'withdrawn':1234,'pending':0,'blacklisted':250} if kind=='withdrawals' else {}})
    local.route('**/api/v1/withdrawals?*', listing)
    local.route('**/api/v1/subsidies?*', listing)
    local.route('**/api/v1/member-filter-options/**', lambda route: route.fulfill(json={'total': 12, 'items': [{'id': 7200 + i, 'name': f'Game {i:02d}'} for i in range(10)]}))
    base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
    ref.goto(base + '/index/login')
    ref.fill('[name=username]', '18532306918'); ref.fill('[name=password]', '123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="tixian?ref=addtabs"]').wait_for(state='attached')
    local.goto('http://127.0.0.1:3000/#withdrawals')
    local.fill('#loginForm [name=username]', '18532306918'); local.fill('#loginForm [name=password]', '123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    measure = '''es=>es.map(e=>{const c=getComputedStyle(e);return {text:e.textContent.trim(),rect:e.getBoundingClientRect().toJSON(),font:c.font,padding:c.padding,margin:c.margin,border:[c.borderTop,c.borderRight,c.borderBottom,c.borderLeft],radius:c.borderRadius,color:c.color,background:c.backgroundColor,display:c.display,gap:c.gap}})'''
    for remote, kind in [('tixian', 'withdrawals'), ('butie', 'subsidies')]:
        ref.goto(base + '/' + remote, wait_until='networkidle')
        local.evaluate('(kind)=>location.hash=kind', kind)
        expect(local.locator('#reviewFilters')).to_have_attribute('data-review-kind', kind)
        for key in ['game', 'agent']:
            ref.locator('[name="' + key + '.name_text"]').click()
            local.locator('[data-review-lookup=' + key + '_id]').click()
            for page in [ref, local]:
                expect(page.locator('.sp_result_area:visible li[pkey]')).to_have_count(10)
                page.mouse.move(0, 0)
            r = ref.locator('.sp_result_area:visible'); l = local.locator('.sp_result_area:visible')
            r.screenshot(path=str(out / f'{kind}-{key}-reference.png'))
            l.screenshot(path=str(out / f'{kind}-{key}-local.png'))
            a = Image.open(out / f'{kind}-{key}-reference.png').convert('RGB')
            b = Image.open(out / f'{kind}-{key}-local.png').convert('RGB')
            assert a.size == b.size, (kind, key, a.size, b.size)
            d = ImageChops.difference(a, b)
            results[kind + '-' + key] = {'mean_rgb': sum(ImageStat.Stat(d).mean)/3, 'changed_pixel_ratio': sum(max(px)>10 for px in d.get_flattened_data())/(a.width*a.height)}
            ref.locator('[name=user_id]').click(); local.locator('#reviewFilters [name=user_id]').click()
        ref.locator('button[name=commonSearch]').click(); local.locator('#reviewSearchToggle').click()
        ref.locator('[name=user_id]').wait_for(state='hidden')
        results[kind] = {}
        if kind=='withdrawals':
            for label,r,l in [('transfer','#toolbar .btn-alipay:not(.hide)','#withdrawalBatchTransfer'),
                              ('summary','#toolbar a:has(#tixian1)','#content [data-withdrawal-summary=withdrawn]')]:
                results[kind][label]={'reference':ref.locator(r).evaluate_all(measure),'local':local.locator(l).evaluate_all(measure)}
                ref.locator(r).screenshot(path=str(out/f'{kind}-{label}-reference.png'))
                local.locator(l).screenshot(path=str(out/f'{kind}-{label}-local.png'))
        for label, r, l in [
            ('tabs', '.nav-tabs>li>a', '.withdrawal-tabs>button'),
            ('tools', '.fixed-table-toolbar .columns button,.fixed-table-toolbar button[name=commonSearch]', '#reviewViewToggle,.withdrawal-columns summary,.review-export summary,#reviewSearchToggle'),
            ('pagination', '.fixed-table-pagination', '.withdrawal-panel .pagination'),
            ('panel', '.panel', '.withdrawal-panel')
        ]:
            results[kind][label] = {'reference': ref.locator(r).evaluate_all(measure), 'local': local.locator(l).evaluate_all(measure)}
            if label in ('tabs', 'tools', 'pagination'):
                for side, page in [('reference', ref), ('local', local)]:
                    rects = [item['rect'] for item in results[kind][label][side]]
                    x, y = min(rect['x'] for rect in rects), min(rect['y'] for rect in rects)
                    width = max(rect['right'] for rect in rects) - x
                    height = max(rect['bottom'] for rect in rects) - y
                    page.mouse.move(0, 0)
                    page.screenshot(path=str(out / f'{kind}-{label}-{side}.png'), clip={'x': x, 'y': y, 'width': width, 'height': height})
                a = Image.open(out / f'{kind}-{label}-reference.png').convert('RGB')
                b = Image.open(out / f'{kind}-{label}-local.png').convert('RGB')
                assert a.size == b.size, (kind, label, a.size, b.size)
                d = ImageChops.difference(a, b)
                d.save(out / f'{kind}-{label}-diff.png')
                results[kind][label]['changed_pixel_ratio'] = sum(max(px)>10 for px in d.get_flattened_data())/(a.width*a.height)
    browser.close()
(out / 'report.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print({key: value for key, value in results.items() if '-' in key})
