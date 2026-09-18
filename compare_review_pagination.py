"""Read-only reference pagination comparison with identical browser fixtures."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright, expect

out = Path('visual-baseline/fixtures/review-pagination')
out.mkdir(parents=True, exist_ok=True)
seeds = {kind: json.loads(Path(f'visual-baseline/fixtures/{kind}/data.json').read_text(encoding='utf-8')) for kind in ('withdrawals', 'subsidies')}
results, queries = [], []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ref = browser.new_page(viewport={'width': 1690, 'height': 1030})
    local = browser.new_page(viewport={'width': 1920, 'height': 1080})
    def reference(route):
        req = route.request
        path = urlparse(req.url).path
        for remote, kind in [('tixian', 'withdrawals'), ('butie', 'subsidies')]:
            if path.endswith('/' + remote + '/index') and req.resource_type in ('xhr', 'fetch'):
                q = parse_qs(urlparse(req.url).query)
                offset, limit = int(q.get('offset', ['0'])[0]), int(q.get('limit', ['10'])[0])
                rows = [{**seeds[kind]['reference'][0], 'id': 9200+i, 'pics': []} for i in range(offset, min(205, offset+limit))]
                return route.fulfill(json={'total': 205, 'rows': rows, 'extend': {'tixian1': 0, 'tixian2': 0}})
        if req.method not in ('GET', 'HEAD') and not path.endswith('/index/login'):
            return route.abort()
        route.continue_()
    def listing(route):
        kind = urlparse(route.request.url).path.rsplit('/', 1)[-1]
        q = parse_qs(urlparse(route.request.url).query); queries.append(q)
        offset, limit = int(q['offset'][0]), int(q['limit'][0])
        rows = [{**seeds[kind]['local'][0], 'id': 9200+i, 'pics': []} for i in range(offset, min(205, offset+limit))]
        route.fulfill(json={'total': 205, 'items': rows, 'summary': {}})
    ref.route('**/*', reference)
    local.route('**/api/v1/withdrawals?*', listing)
    local.route('**/api/v1/subsidies?*', listing)
    base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
    ref.goto(base + '/index/login')
    ref.fill('[name=username]', '18532306918'); ref.fill('[name=password]', '123456')
    ref.locator('button[type=submit],input[type=submit]').first.click()
    ref.locator('a[href*="tixian?ref=addtabs"]').wait_for(state='attached')
    local.goto('http://127.0.0.1:3000/#withdrawals')
    local.fill('#loginForm [name=username]', '18532306918'); local.fill('#loginForm [name=password]', '123456')
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    for remote, kind in [('tixian', 'withdrawals'), ('butie', 'subsidies')]:
        ref.goto(base + '/' + remote, wait_until='networkidle')
        ref.locator('button[name=commonSearch]').click()
        ref.locator('[name=user_id]').wait_for(state='hidden')
        local.evaluate('(kind)=>location.hash=kind', kind)
        expect(local.locator('#reviewFilters')).to_have_attribute('data-review-kind', kind)
        local.locator('#reviewSearchToggle').click()
        first = local.locator('[data-review-cell=id]').first
        for number in [1, 2, 4, 5, 10, 19, 20, 21]:
            with ref.expect_response('**/' + remote + '/index?*'):
                ref.evaluate('n=>jQuery("#table").bootstrapTable("selectPage",n)', number)
            expect(ref.locator('#table tbody tr[data-index] td').nth(1)).to_have_text(str(9200+(number-1)*10))
            if number != 1:
                local.locator('[aria-label="跳转页码"]').fill(str(number))
                local.locator('[data-review-jump]').click()
            expect(first).to_have_text(str(9200+(number-1)*10), use_inner_text=True)
            a_panel, b_panel = ref.locator('.fixed-table-pagination'), local.locator('.withdrawal-panel .pagination')
            assert ''.join(a_panel.inner_text().split()) == ''.join(b_panel.inner_text().split())
            for side, page, panel in [('reference', ref, a_panel), ('local', local, b_panel)]:
                page.mouse.move(0, 0)
                panel.screenshot(path=str(out / f'{kind}-{number}-{side}.png'))
            a = Image.open(out / f'{kind}-{number}-reference.png').convert('RGB')
            b = Image.open(out / f'{kind}-{number}-local.png').convert('RGB')
            assert a.size == b.size, (kind, number, a.size, b.size)
            d = ImageChops.difference(a, b)
            d.save(out / f'{kind}-{number}-diff.png')
            results.append({'kind': kind, 'page': number, 'mean_rgb': sum(ImageStat.Stat(d).mean)/3,
                            'changed_pixel_ratio': sum(max(px)>10 for px in d.get_flattened_data())/(a.width*a.height)})
            if number == 1:
                measure = '''es=>es.map(e=>({tag:e.tagName,text:e.textContent,rect:e.getBoundingClientRect().toJSON(),font:getComputedStyle(e).font,verticalAlign:getComputedStyle(e).verticalAlign}))'''
                results[-1]['reference_jump'] = ref.locator('.fixed-table-pagination input,.fixed-table-pagination .jumpto button').evaluate_all(measure)
                results[-1]['local_jump'] = local.locator('.pagination nav input,[data-review-jump]').evaluate_all(measure)
        local.locator('#reviewNext').click(); expect(first).to_have_text('9200', use_inner_text=True)
        local.locator('#reviewPrev').click(); expect(first).to_have_text('9400', use_inner_text=True)
        before = len(queries)
        local.locator('#reviewPageSizeMenu summary').click()
        expect(local.locator('[data-review-size]')).to_have_count(6)
        local.locator('[data-review-size=All]').click()
        expect(local.locator('[data-review-cell=id]')).to_have_count(205)
        expect(local.locator('.pagination nav')).to_be_hidden()
        assert [q['offset'] for q in queries[before:]] == [['0'], ['200']]
        local.reload()
        expect(local.locator('[data-review-cell=id]')).to_have_count(205)
        expect(local.locator('#reviewPageSizeMenu summary')).to_have_text('All')
        local.locator('#reviewPageSizeMenu summary').click()
        local.locator('[data-review-size="10"]').click()
        expect(local.locator('[data-review-cell=id]')).to_have_count(10)
    browser.close()
(out / 'report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(results)
print('PASS: both review page windows, jump, cyclic boundaries, All batches and persistence')
