"""Reference-backed multi-APP filters, links and immutable scope in browser fixtures."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright


reference=json.loads(Path('visual-baseline/reference-verified/member-behavior-tables.json').read_text(encoding='utf-8'))
mapping={'game.name':'game_name','create_time':'created_range','update_time':'updated_range',
         'date':'date_range','user.is_white':'is_white','tag':'tags','good.name':'good_name'}
keys=['lottery','risk','income','coins','withdrawals','members','logins','addresses']
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1536,'height':1000},accept_downloads=True)
    errors=[];queries=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    rows=[dict(id=i,user_id=42,username='fixture',game_id=237,game_name='fixture game %_',status=1,
        is_white=1,network_status=0,coin=i,coin_before=10,coin_after=10+i,type=30,remark='fixture remark',
        lottery_price=i,ecpm=2,created_at='2026-09-17T04:00:00Z',date='2026-09-17',
        exchange_value=25,receive_name='recipient',receive_tel='fixture phone',receive_address='address',
        default_status=1,ip='192.0.2.1') for i in range(1,24)]

    def api(route):
        parsed=urlparse(route.request.url)
        if parsed.path=='/api/auth/login':
            route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert route.request.method=='GET',route.request.url
        query={key:value[0] for key,value in parse_qs(parsed.query).items()}
        queries.append((parsed.path,query))
        offset=int(query.get('offset',0));limit=int(query.get('limit',10))
        route.fulfill(json={'total':len(rows),'items':rows[offset:offset+limit],
            'member_summary':{'coin_user':100,'coin':50,'freeze_coin':5},
            'summary':{'change':276,'withdrawn':10,'pending':5}})

    page.route('**/api/**',api)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('form=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.evaluate("openMemberBehavior(42,237,'multiple')")
    dialog=page.locator('.member-behavior-dialog')

    def active(key):
        dialog.locator(f'[data-behavior-tab={key}]').click()
        page.wait_for_function('key=>document.querySelector("#behavior-pane-"+key+" tbody") && !document.querySelector("#behavior-pane-"+key+" .game-user-results").hasAttribute("aria-busy")',arg=key)
        return dialog.locator('#behavior-pane-'+key)

    def latest(endpoint):
        return [query for path,query in queries if path.endswith(endpoint)][-1]

    for key,definition in zip(keys,reference['duoge']):
        pane=active(key)
        expected=[column['title'] for column in definition['columns'] if column.get('visible',True) and column.get('field') not in (0,'operate')]
        actual=pane.locator('thead th').all_text_contents()
        if key=='withdrawals':actual=actual[1:-1]
        assert actual==expected,(key,actual,expected)
        filters=pane.locator('.ads-filters [name]').evaluate_all('els=>els.map(el=>el.name)')
        expected_filters=[mapping.get(column['field'],column['field']) for column in definition['columns'] if column.get('operate') and column.get('field') not in (0,'operate')]
        assert filters==expected_filters,(key,filters,expected_filters)
        search_fields=pane.locator('tbody [data-search-field]').evaluate_all('els=>[...new Set(els.map(el=>el.dataset.searchField))]')
        expected_links=[mapping.get(column['field'],column['field']) for column in definition['columns'] if column.get('visible',True) and 'searchit' in (column.get('formatter') or '')]
        assert search_fields==expected_links,(key,search_fields,expected_links)
        endpoint=queries[-1][0]
        pane.locator('[data-action=search]').click()
        pane.locator('[name=game_name]').fill('fixture %_')
        if 'user_id' in filters:pane.locator('[name=user_id]').fill('99')
        with page.expect_response('**'+endpoint+'?*'):
            pane.locator('form [type=submit]').click()
        query=latest(endpoint)
        assert 'game_id' not in query
        scope='parent_id' if key=='members' else 'member_id' if key=='risk' else 'user_id'
        assert query[scope]=='42'
        assert query['game_name_contains' if key=='members' else 'game_name']=='fixture %_'
        if 'user_id' in filters:assert query['filter_user_id']=='99'
        with page.expect_response('**'+endpoint+'?*'):
            pane.locator('tbody [data-search-field=game_name]').first.click()
        assert latest(endpoint)['game_name_contains' if key=='members' else 'game_name']=='fixture game %_'
        if 'user_id' in filters:
            with page.expect_response('**'+endpoint+'?*'):
                pane.locator('tbody [data-search-field=user_id]').first.click()
            assert latest(endpoint)['filter_user_id']=='42'

    coins=active('coins')
    coins.locator('[name=user_id]').fill('99')
    with page.expect_response('**/coin-logs?*'):coins.locator('form [type=submit]').click()
    coins.locator('.game-user-export summary').click()
    with page.expect_download() as downloaded:
        coins.locator('[data-export=json]').click()
    payload=json.loads(Path(downloaded.value.path()).read_text(encoding='utf-8-sig'))
    assert len(payload['data'])==23
    assert latest('/coin-logs')['filter_user_id']=='99' and latest('/coin-logs')['user_id']=='42'
    assert latest('/coin-logs')['game_name']=='fixture game %_'
    active('income');coins=active('coins')
    assert coins.locator('[name=user_id]').input_value()=='99'
    with page.expect_response('**/coin-logs?*'):coins.locator('form [type=reset]').click()
    assert 'filter_user_id' not in latest('/coin-logs') and 'game_name' not in latest('/coin-logs')
    assert latest('/coin-logs')['user_id']=='42'
    pane=active('lottery')
    output=Path('visual-baseline/verified');output.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(output/'member-behavior-multi-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert dialog.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    assert pane.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    pane.locator('[name=game_name]').scroll_into_view_if_needed()
    page.screenshot(path=str(output/'member-behavior-multi-mobile.png'))
    dialog.locator('[data-behavior-close]').click();dialog.wait_for(state='detached')
    page.evaluate("openMemberBehavior(42,237,'single')")
    for key,definition in zip(keys,reference['yige']):
        pane=active(key)
        assert pane.locator('.ads-filters [name=user_id],.ads-filters [name=game_name]').count()==0
        assert latest(queries[-1][0])['game_id']=='237'
    page.evaluate("location.hash='games'")
    dialog.wait_for(state='detached')
    assert not errors,errors
    browser.close()

print('Multi-APP behavior: all reference columns/filters/search links, scope intersection, preserved/reset filters, export, mobile and single-APP isolation passed')
