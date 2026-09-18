"""Reference-backed behavior columns and browser interactions, with API fixtures."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

reference=json.loads(Path('visual-baseline/reference-verified/member-behavior-tables.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080},accept_downloads=True)
    errors=[];queries=[];mode={'fail':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    rows=[dict(id=i,user_id=42,username='fixture',game_id=237,game_name='fixture game',status=1,is_white=1,
               network_status=0,coin=i,coin_before=100,coin_after=100+i,type=30,remark='fixture remark',
               lottery_price=i,ecpm=2,created_at='2026-09-17T04:00:00Z',date='2026-09-17',
               exchange_value=25,receive_name='recipient',receive_address='address',default_status=1)
          for i in range(1,24)]
    def api(route):
        url=urlparse(route.request.url)
        if url.path=='/api/auth/login':
            route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        assert route.request.method=='GET',route.request.url
        query={k:v[0] for k,v in parse_qs(url.query).items()}
        queries.append((url.path,query))
        if mode['fail']:
            mode['fail']=False;route.fulfill(status=403,json={'detail':'fixture denied'});return
        offset=int(query.get('offset',0));limit=int(query.get('limit',10))
        route.fulfill(json={'total':len(rows),'items':rows[offset:offset+limit],
                            'member_summary':{'coin_user':1234,'coin':123,'freeze_coin':3},
                            'summary':{'change':276,'total_coin':25,'pending_coin':25}})
    page.route('**/api/**',api)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.evaluate("openMemberBehavior(42,237,'single')")
    dialog=page.locator('.member-behavior-dialog')
    keys=['lottery','risk','income','coins','withdrawals','members','logins','addresses']
    def active(key):
        dialog.locator(f'[data-behavior-tab={key}]').click()
        pane=dialog.locator(f'#behavior-pane-{key}')
        page.wait_for_function('(key)=>!!document.querySelector("#behavior-pane-"+key+" tbody") && !document.querySelector("#behavior-pane-"+key+" .game-user-results").hasAttribute("aria-busy")',arg=key)
        return pane
    for key,definition in zip(keys,reference['yige']):
        pane=active(key)
        expected=[column['title'] for column in definition['columns'] if column.get('visible',True) and column.get('field') not in (0,'operate')]
        actual=pane.locator('thead th').all_text_contents()
        if key=='withdrawals':actual=actual[1:-1]
        assert actual==expected,(key,actual,expected)
        filters=pane.locator('.ads-filters [name]').evaluate_all('els=>els.map(el=>el.name)')
        mapping={'create_time':'created_range','update_time':'updated_range','date':'date_range','user.is_white':'is_white','tag':'tags','good.name':'good_name'}
        expected_filters=[mapping.get(column['field'],column['field']) for column in definition['columns'] if column.get('operate') and column.get('field') not in (0,'operate')]
        assert filters==expected_filters,(key,filters,expected_filters)
        query=queries[-1][1]
        assert query['game_id']=='237'
        assert query['parent_id' if key=='members' else 'member_id' if key=='risk' else 'user_id']=='42'
        if key=='members':assert 'user_id' not in query and pane.locator('[data-game-member-edit]').count()==0
        if key=='withdrawals':assert '2.5元' in pane.locator('tbody').inner_text()
    coins=active('coins')
    assert '兑换' in coins.locator('tbody').inner_text()
    assert '276' in coins.locator('.behavior-coin-summary').inner_text()
    assert coins.locator('.behavior-balances strong').all_text_contents()==['1234','123','3']
    coins.locator('[data-action=search]').click()
    coins.locator('[name=type]').select_option('30')
    coins.locator('[name=remark]').fill('fixture')
    coins.locator('[name=created_range]').fill('2026-09-17 00:00:00 - 2026-09-17 23:59:59')
    dialog.locator('.daterangepicker:visible').wait_for()
    page.keyboard.press('Escape')
    with page.expect_response('**/api/v1/coin-logs?*'):
        coins.locator('form [type=submit]').click()
    assert queries[-1][1]['type']=='30' and queries[-1][1]['remark']=='fixture'
    assert queries[-1][1]['created_from']=='2026-09-16T16:00:00.000Z'
    coins.locator('[data-sort=coin]').click()
    page.wait_for_function("document.querySelector('#behavior-pane-coins [data-sort=coin]').parentElement.getAttribute('aria-sort')==='descending'")
    coins.locator('[aria-label="下一页"]').click()
    page.wait_for_function("document.querySelector('#behavior-pane-coins [aria-current=page]').textContent==='2'")
    active('lottery');coins=active('coins')
    assert queries[-1][1]['offset']=='10' and queries[-1][1]['type']=='30'
    assert coins.locator('[name=remark]').input_value()=='fixture'
    mode['fail']=True
    coins.locator('[data-action=refresh]').click()
    coins.locator('[role=alert]').get_by_text('fixture denied').wait_for()
    assert coins.locator('tbody tr').count()==10
    coins.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('#behavior-pane-coins [role=alert]').textContent===''")
    coins.locator('.game-user-columns summary').click()
    coins.locator('[data-column=coin_before]').uncheck()
    coins.locator('.game-user-columns summary').click()
    coins.locator('[data-action=cards]').click()
    assert coins.locator('.game-user-cards article').count()==10
    coins.locator('[data-action=cards]').click()
    coins.locator('.game-user-export summary').click()
    with page.expect_download() as download:
        coins.locator('[data-export=json]').click()
    exported=json.loads(Path(download.value.path()).read_text(encoding='utf-8-sig'))
    assert len(exported['data'])==23
    assert queries[-1][1]['user_id']=='42' and queries[-1][1]['game_id']=='237' and queries[-1][1]['type']=='30'
    assert '金币变动前' not in exported['data'][0]
    coins.locator('[name=created_range]').focus()
    dialog.locator('.daterangepicker:visible').wait_for()
    active('income')
    assert dialog.locator('.daterangepicker:visible').count()==0
    income=dialog.locator('#behavior-pane-income')
    income.locator('[data-action=search]').click()
    income.locator('[name=date_range]').fill('2026-09-17 00:00:00 - 2026-09-18 23:59:59')
    dialog.locator('.daterangepicker:visible').wait_for()
    page.keyboard.press('Escape')
    with page.expect_response('**/api/v1/member-daily-income?*'):
        income.locator('form [type=submit]').click()
    assert queries[-1][1]['date_from']=='2026-09-17' and 'created_from' not in queries[-1][1]
    active('coins')
    out=Path('visual-baseline/verified');out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'member-behavior-coins.png'))
    page.set_viewport_size({'width':390,'height':844})
    coins.locator('[data-action=search]').click()
    coins.locator('[data-action=cards]').click()
    assert dialog.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    assert coins.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path=str(out/'member-behavior-mobile.png'))
    dialog.locator('[data-behavior-close]').click()
    dialog.wait_for(state='detached')
    page.wait_for_function('reviewDateBindings.size===0')
    page.evaluate("openMemberBehavior(42,237,'multiple')")
    risk=active('risk')
    assert queries[-1][1]['member_id']=='42' and 'game_id' not in queries[-1][1]
    assert '会员ID' not in risk.locator('thead').inner_text()
    page.evaluate("location.hash='games'")
    dialog.wait_for(state='detached')
    assert not errors,errors
    browser.close()
print('Behavior UI: reference single-app columns/filters, exact scopes, types/units, dates, retained tabs, sort/page/export, retry, mobile and cleanup passed')
