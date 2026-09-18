"""Capture read-only behavior table definitions, without personal row data."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path('visual-baseline/reference-verified')
base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1536, 'height': 822})
    page.goto(base + '/index/login')
    page.fill('[name=username]', '18532306918')
    page.fill('[name=password]', '123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_url(lambda url: '/index/login' not in url)
    response = page.request.get(base + '/gameuser/index', params={
        'limit': 1, 'offset': 0, 'sort': 'coin_user', 'order': 'desc', 'filter': '{}', 'op': '{}'},
        headers={'X-Requested-With': 'XMLHttpRequest'})
    member = response.json()['rows'][0]
    user_id = member['id']
    def readonly(route):
        if route.request.method not in ('GET', 'HEAD') or any(action in route.request.url for action in ('imeiidban','deviceidban','/del/','/multi/')):
            route.abort()
        elif route.request.resource_type in ('xhr', 'fetch'):
            route.fulfill(json={'total': 0, 'rows': [], 'extend': {'coin': 0}})
        else:
            route.continue_()
    page.route('**/*', readonly)
    def save_controller(response):
        if '/backend/users/' in response.url and '.js' in response.url:
            name = response.url.split('/backend/users/')[1].split('?')[0].replace('/', '-')
            (out / ('behavior-' + name)).write_text(response.text(), encoding='utf-8')
    page.on('response', save_controller)
    evidence = {}
    for scope in ('yige', 'duoge'):
        page.goto(base + f'/users/{scope}/index/user_id/{user_id}', wait_until='networkidle')
        tabs = page.locator('.nav-tabs a')
        evidence[scope] = []
        for index in range(tabs.count()):
            tabs.nth(index).click()
            pane = tabs.nth(index).get_attribute('href')
            table = page.locator(pane + ' table[id^=table]').first
            table.wait_for(state='attached')
            page.wait_for_function("id=>!!jQuery('#'+id).data('bootstrap.table')", arg=table.get_attribute('id'))
            item = table.evaluate('''el=>{
                const o=jQuery(el).bootstrapTable('getOptions');
                return {table:el.id,url:o.url.replace(/user_id\\/\\d+/g,'user_id/FIXTURE'),
                  sortName:o.sortName,sortOrder:o.sortOrder,pageList:o.pageList,pageSize:o.pageSize,
                  columns:o.columns.flat().map(c=>({field:c.field,title:c.title,visible:c.visible,
                    sortable:c.sortable,operate:c.operate,align:c.align,addclass:c.addclass,
                    searchList:c.searchList,formatter:c.formatter?.toString()}))};
            }''')
            item['label'] = tabs.nth(index).inner_text()
            item['filters'] = page.locator(pane + ' .commonsearch-table .form-group').evaluate_all('''els=>els.map(el=>({
                label:el.querySelector('label')?.textContent.trim(),
                controls:[...el.querySelectorAll('input,select')].map(n=>({name:n.name,type:n.type,placeholder:n.placeholder,
                    options:n.tagName==='SELECT'?[...n.options].map(o=>({value:o.value,text:o.textContent})):undefined}))}))''')
            evidence[scope].append(item)
    (out / 'member-behavior-tables.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    scope_evidence = []
    for endpoint in ('lottery', 'coinlog', 'coinday', 'loginlog', 'distribution'):
        for multi in (False, True):
            response = page.request.get(base + f'/users/{endpoint}/index/user_id/{user_id}' + ('/type/1' if multi else ''),
                params={'limit': 20, 'offset': 0, 'sort': 'id', 'order': 'desc', 'filter': '{}', 'op': '{}'},
                headers={'X-Requested-With': 'XMLHttpRequest'})
            data = response.json()
            rows = data.get('rows', [])
            scope_evidence.append(dict(endpoint=endpoint,multiple=multi,total=data.get('total'),
                count=len(rows),distinct_user_ids=len({r.get('user_id') for r in rows}),
                distinct_game_ids=len({r.get('game_id') for r in rows}),
                all_selected_user=all(r.get('user_id')==user_id for r in rows) if rows else None,
                all_selected_username=all(r.get('user', {}).get('username')==member.get('username') for r in rows) if rows else None,
                keys=sorted(rows[0]) if rows else []))
    (out / 'member-behavior-scope.json').write_text(json.dumps(scope_evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    candidates = page.request.get(base + '/gameuser/index', params={
        'limit': 30, 'offset': 0, 'sort': 'coin_user', 'order': 'desc', 'filter': '{}', 'op': '{}'},
        headers={'X-Requested-With': 'XMLHttpRequest'}).json().get('rows', [])
    usernames = {}
    for candidate in candidates:
        if candidate.get('username'):
            usernames.setdefault(candidate['username'], []).append(candidate)
    repeated = [candidate for group in usernames.values() if len(group) > 1 for candidate in group]
    selected = {candidate['id']: candidate for candidate in [*repeated, *candidates]}
    probes = []
    for sample, candidate in enumerate(list(selected.values())[:6]):
        for endpoint in ('lottery', 'coinlog', 'loginlog'):
            results = []
            for multi in (False, True):
                data = page.request.get(base + f'/users/{endpoint}/index/user_id/{candidate["id"]}' + ('/type/1' if multi else ''),
                    params={'limit': 20, 'offset': 0, 'sort': 'id', 'order': 'desc', 'filter': '{}', 'op': '{}'},
                    headers={'X-Requested-With': 'XMLHttpRequest'}).json()
                records = data.get('rows', [])
                results.append({'multiple':multi,'total':data.get('total'),'sample_count':len(records),
                    'distinct_members':len({row.get('user_id') for row in records}),
                    'outside_selected_member':sum(row.get('user_id') != candidate['id'] for row in records),
                    'all_same_username':all(row.get('user', {}).get('username') == candidate.get('username') for row in records) if records else None})
            probes.append({'sample':sample,'endpoint':endpoint,'results':results})
    (out / 'member-behavior-scope-probes.json').write_text(json.dumps({
        'candidate_count':len(candidates),'repeated_username_groups':sum(len(group)>1 for group in usernames.values()),
        'probes':probes}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
print('Reference behavior definitions saved; business writes blocked, row values excluded')
