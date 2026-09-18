"""Game member switch regressions with all mutation requests intercepted."""
from urllib.parse import urlparse, parse_qs
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];writes=[];queries=[];fail={'value':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.goto('http://127.0.0.1:3000/#games',wait_until='networkidle')
    page.locator('[data-game-user]').first.wait_for()
    gid=int(page.locator('[data-game-user]').first.get_attribute('data-game-user'))
    row={'id':987654,'username':'fixture','name':'hidden nickname','parent_id':100,'parent_name':'parent',
         'parent_username':'parent-account','game_id':gid,'game_name':'fixture game','is_white':0,'status':1,
         'exchange_enable':1,'coin':12.5,'freeze_coin':3,'game_addiction_time':'2026-09-17 12:00:00','created_at':'2025-01-01T16:00:00','last_login_time':'2025-01-02T16:00:00'}
    def members(route):
        if route.request.method=='GET':
            if urlparse(route.request.url).path.endswith('/987654'):
                route.fulfill(json=row);return
            query=parse_qs(urlparse(route.request.url).query)
            queries.append(query)
            assert query['game_id']==[str(gid)]
            route.fulfill(json={'items':[row],'total':1})
        else:
            assert route.request.method=='PATCH'
            assert urlparse(route.request.url).path.endswith('/987654')
            changes=route.request.post_data_json;writes.append(changes)
            if fail['value']:
                fail['value']=False
                route.fulfill(status=403,json={'detail':'权限不足'})
            else:
                row.update(changes);route.fulfill(json=row)
    page.route('**/api/v1/members**',members)
    batches=[]
    def batch(route):
        assert route.request.method=='POST'
        assert urlparse(route.request.url).path==f'/api/v1/games/{gid}/members/batch-status'
        body=route.request.post_data_json
        assert body['ids']==[row['id']]
        batches.append(body)
        if fail['value']:
            fail['value']=False;route.fulfill(status=403,json={'detail':'权限不足'})
        else:
            row['status']=body['status'];route.fulfill(json={'updated':1})
    page.route('**/api/v1/games/*/members/batch-status',batch)
    page.locator('[data-game-user]').first.click()
    page.locator('[data-tab=four]').click()
    pane=page.locator('#game-user-pane-four')
    pane.locator('[data-member-toggle=is_white]').wait_for()
    pane.locator('[data-member-behavior]').first.click()
    behavior=page.locator('.member-behavior-dialog')
    behavior.locator('[role=tab]').first.wait_for()
    assert behavior.locator('[role=tab]').all_text_contents()==['\u62bd\u5956\u5217\u8868','\u98ce\u63a7\u5386\u53f2','\u6bcf\u65e5\u6536\u76ca','\u91d1\u5e01\u6d41\u6c34','\u63d0\u73b0\u8bb0\u5f55','\u5206\u9500\u7528\u6237','\u767b\u9646\u5386\u53f2','\u6536\u8d27\u5730\u5740']
    assert behavior.get_attribute('aria-label')=='\u5355APP\u884c\u4e3a'
    behavior.locator('[data-behavior-tab=coins]').click()
    page.locator('.member-behavior-dialog main').wait_for()
    behavior.locator('[data-behavior-tab=addresses]').click()
    page.wait_for_timeout(300)
    assert behavior.locator('main .behavior-empty, main .table-wrap, main .behavior-error').count()>=1
    behavior.locator('header button').click()
    behavior.wait_for(state='detached')
    pane.locator('[data-member-behavior]').nth(1).click()
    assert page.locator('.member-behavior-dialog').get_attribute('aria-label')=='\u591aAPP\u884c\u4e3a'
    page.locator('.member-behavior-dialog header button').click()
    page.locator('.member-behavior-dialog').wait_for(state='detached')
    assert pane.locator('thead').inner_text().find('上级昵称')>=0
    assert '昵称' not in pane.locator('thead').inner_text().replace('上级昵称','')
    pane.locator('[data-member-toggle=is_white]').click()
    page.wait_for_function("document.querySelector('[data-member-toggle=is_white]').getAttribute('aria-checked')==='true'")
    assert writes==[{'is_white':1}]
    fail['value']=True
    pane.locator('[data-member-toggle=status]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-four [role=alert]').textContent==='权限不足'")
    assert pane.locator('[data-member-toggle=status]').get_attribute('aria-checked')=='true'
    pane.locator('[data-member-toggle=status]').click()
    page.wait_for_function("document.querySelector('[data-member-toggle=status]').getAttribute('aria-checked')==='false'")
    pane.locator('.game-user-columns summary').click()
    pane.locator('[data-column=exchange_enable]').check()
    pane.locator('[data-column=parent_username]').check()
    pane.locator('[data-column=game_addiction_time]').check()
    pane.locator('.game-user-columns summary').click()
    assert 'parent-account' in pane.locator('tbody').inner_text()
    assert '2026-09-17 12:00:00' in pane.locator('tbody').inner_text()
    pane.locator('[data-sort=game_addiction_time]').click()
    page.wait_for_function("document.querySelector('[data-sort=game_addiction_time]').parentElement.getAttribute('aria-sort')==='descending'")
    assert queries[-1]['sort']==['game_addiction_time']
    pane.locator('[data-action=search]').click()
    pane.locator('[name=game_addiction_range]').fill('2026-09-17 12:00:00 - 2026-09-17 12:00:00')
    page.keyboard.press('Escape')
    with page.expect_response('**/api/v1/members?*'):
        pane.locator('[type=submit]').click()
    assert queries[-1]['game_addiction_time']==['2026-09-17 12:00:00 - 2026-09-17 12:00:00']
    assert 'created_from' not in queries[-1]
    pane.locator('.game-user-export summary').click()
    with page.expect_download() as download:
        pane.locator('[data-export=json]').click()
    exported=Path(download.value.path()).read_text(encoding='utf-8-sig')
    assert len(json.loads(exported)['data'])==1
    assert 'fixture' in exported and 'parent-account' in exported
    assert '单APP行为' not in exported and '修改金币' not in exported and '<button' not in exported
    pane.locator('[data-action=cards]').click()
    pane.locator('[data-member-toggle=exchange_enable]').click()
    page.wait_for_function("document.querySelector('[data-member-toggle=exchange_enable]').getAttribute('aria-checked')==='false'")
    assert writes[-1]=={'exchange_enable':0}
    assert pane.locator('.game-user-cards').count()==1
    assert pane.locator('[data-member-batch="1"]').is_disabled()
    pane.locator('[data-member-select]').check()
    pane.locator('[data-action=cards]').click()
    assert pane.locator('[data-member-select]').is_checked()
    fail['value']=True
    pane.locator('.game-member-more summary').click()
    pane.locator('[data-member-batch="1"]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-four [role=alert]').textContent==='权限不足'")
    assert pane.locator('[data-member-select]').is_checked()
    pane.locator('.game-member-more summary').click()
    pane.locator('[data-member-batch="1"]').click()
    page.wait_for_function("document.querySelector('[data-member-toggle=status]').getAttribute('aria-checked')==='true'")
    assert not pane.locator('[data-member-select]').is_checked()
    assert batches[-1]=={'ids':[987654],'status':1}
    pane.locator('[data-member-select-all]').check()
    pane.locator('.game-member-more summary').click()
    pane.locator('[data-member-batch="0"]').click()
    page.wait_for_function("document.querySelector('[data-member-toggle=status]').getAttribute('aria-checked')==='false'")
    assert batches[-1]=={'ids':[987654],'status':0}
    pane.locator('[data-member-coins]').click()
    editor=page.locator('.game-coin-dialog')
    editor.locator('[type=submit]').wait_for()
    page.wait_for_function("document.querySelector('.game-coin-dialog [name=coin]').value==='12.5'")
    editor.locator('[name=coin]').fill('99')
    editor.locator('[type=reset]').click()
    assert editor.locator('[name=coin]').input_value()=='12.5'
    editor.locator('[name=coin]').fill('25.75')
    editor.locator('[name=freeze_coin]').fill('4.5')
    fail['value']=True
    editor.locator('[type=submit]').click()
    page.wait_for_function("document.querySelector('.game-coin-dialog [role=alert]').textContent==='权限不足'")
    assert editor.locator('[name=coin]').input_value()=='25.75'
    assert row['coin']==12.5
    editor.locator('[type=submit]').click()
    editor.wait_for(state='detached')
    assert writes[-1]=={'coin':25.75,'freeze_coin':4.5}
    assert row['coin']==25.75
    pane.locator('[data-member-coins]').click()
    editor.wait_for()
    count=len(writes)
    page.locator('.game-coin-dialog header button').click()
    editor.wait_for(state='detached')
    assert len(writes)==count
    pane.locator('[data-member-coins]').click()
    editor.wait_for()
    page.evaluate("document.querySelector('.game-user-dialog').close()")
    editor.wait_for(state='detached')
    assert len(writes)==count
    page.locator('[data-game-user]').first.click()
    page.locator('[data-tab=four]').click()
    pane.locator('[data-member-toggle=is_white]').wait_for()
    page.screenshot(path='visual-baseline/verified/game-member-switches.png')
    page.set_viewport_size({'width':390,'height':844})
    assert pane.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    pane.locator('[data-action=cards]').click()
    assert pane.locator('[data-member-toggle=is_white]').count()==1
    assert pane.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path='visual-baseline/verified/game-member-mobile.png')
    pane.locator('[data-member-coins]').click()
    editor.wait_for()
    assert editor.evaluate('el=>el.scrollWidth<=el.clientWidth+1 && el.getBoundingClientRect().width<=innerWidth')
    page.screenshot(path='visual-baseline/verified/game-member-coins-mobile.png')
    editor.locator('header button').click()
    editor.wait_for(state='detached')
    page.locator('[data-dialog-close]').click()
    assert errors==[],errors
    browser.close()
    print('Game member flags, hidden columns, permission errors and card switches passed')
