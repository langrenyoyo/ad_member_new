"""Exercise game withdrawal actions with intercepted writes, never business records."""
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    page.goto('http://127.0.0.1:3000/#games',wait_until='networkidle')
    page.locator('[data-game-user]').first.wait_for()
    gid=int(page.locator('[data-game-user]').first.get_attribute('data-game-user'))
    page.evaluate("localStorage.setItem('pagesize','10')")
    rows=[dict(id=i,user_id=900+i,username=f'fixture-{i}',game_id=gid,game_name='fixture',
               exchange_value=125,receive_name='fixture',receive_tel='test',status=0,is_true=1,
               reason='',created_at='2025-01-01T16:00:00',updated_at='2025-01-02T16:00:00') for i in range(1,13)]
    rows[0]['status']=1
    calls=[];queries=[];fail={'status':None}
    def withdrawals(route):
        parsed=urlparse(route.request.url)
        if route.request.method=='GET':
            q={key:values[0] for key,values in parse_qs(parsed.query).items()}
            queries.append(q)
            assert q['game_id']==str(gid)
            filtered=list(rows)
            if 'status' in q:filtered=[r for r in filtered if r['status']==(2 if q['status']=='4' else int(q['status']))]
            filtered.sort(key=lambda r:r[q['sort']],reverse=q['order']=='desc')
            offset=int(q['offset']);limit=int(q['limit'])
            route.fulfill(json={'total':len(filtered),'items':filtered[offset:offset+limit],
                                'summary':{'withdrawn':sum(r['exchange_value'] for r in rows if r['status']==1),
                                           'pending':sum(r['exchange_value'] for r in rows if r['status']==0)}})
            return
        assert route.request.method=='POST', 'Unexpected business write'
        body=route.request.post_data_json
        action=parsed.path.split('/')[-1]
        ids=body['ids'] if action.startswith('batch-') else [int(parsed.path.split('/')[-2])]
        calls.append({'action':action,'ids':ids,'body':body})
        if fail['status']:
            status=fail['status'];fail['status']=None
            route.fulfill(status=status,json={'detail':'审核失败，请刷新后重试'})
            return
        targets=[r for r in rows if r['id'] in ids]
        assert len(targets)==len(ids) and all(r['status']==0 for r in targets)
        for row in targets:
            row['status']=1 if action.endswith('approve') else 2
            row['reason']=body.get('reason','')
        route.fulfill(json={'updated':len(targets)})
    page.route('**/api/v1/withdrawals**',withdrawals)
    page.locator('[data-game-user]').first.click()
    page.locator('[data-tab=third]').click()
    pane=page.locator('#game-user-pane-third')
    pane.locator('tbody tr').first.wait_for()
    assert pane.locator('tbody tr').count()==10
    assert pane.locator('[data-withdrawn]').inner_text()=='125'
    assert pane.locator('[data-pending]').inner_text()=='1375'
    assert '12.5元' in pane.locator('tbody').inner_text()
    assert pane.locator('[data-column=reason]').is_checked() is False
    assert pane.locator('[data-game-batch=approve]').is_disabled()

    # Cancellation is inert; duplicate clicks while confirmation is open cannot send a write.
    pane.locator('[data-game-review=approve][data-review-id="12"]').click()
    page.locator('.withdrawal-confirm [data-cancel]').last.click()
    page.locator('.withdrawal-confirm').wait_for(state='detached')
    assert calls==[]
    pane.locator('[data-game-review=approve][data-review-id="12"]').click()
    page.locator('.withdrawal-confirm [type=submit]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-third [data-withdrawn]').textContent==='250'")
    assert len(calls)==1 and calls[-1]['ids']==[12]
    assert pane.locator('[data-review-id="12"]').count()==0

    pane.locator('[data-game-review=reject][data-review-id="11"]').click()
    reason=page.locator('.withdrawal-confirm textarea')
    reason.fill('   ')
    page.locator('.withdrawal-confirm [type=submit]').click()
    assert len(calls)==1
    reason.fill('  fixture reason  ')
    page.locator('.withdrawal-confirm [type=submit]').click()
    page.wait_for_function("document.querySelectorAll('#game-user-pane-third [data-review-id=\"11\"]').length===0")
    assert calls[-1]['body']=={'reason':'fixture reason'}

    # Error keeps the selection; a retry succeeds and clears it after refresh.
    for number in [10,9]:pane.locator(f'[data-game-select="{number}"]').check()
    fail['status']=403
    pane.locator('[data-game-batch=refuse]').click()
    page.locator('.withdrawal-confirm [type=submit]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-third [role=alert]').textContent.length>0")
    assert pane.locator('[data-game-select="10"]').is_checked()
    pane.locator('[data-game-batch=refuse]').click()
    page.locator('.withdrawal-confirm [type=submit]').click()
    page.wait_for_function("!document.querySelector('#game-user-pane-third [data-game-select=\"10\"]').checked && !document.querySelector('#game-user-pane-third .game-user-results').hasAttribute('aria-busy')")
    assert set(calls[-1]['ids'])=={9,10}
    assert not pane.locator('[data-game-select="10"]').is_checked()
    pane.locator('[data-game-select="8"]').check()
    pane.locator('[data-action=cards]').click()
    assert pane.locator('.game-user-cards [data-game-select="8"]').is_checked()
    pane.locator('[data-game-batch=approve]').click()
    page.locator('.withdrawal-confirm [type=submit]').click()
    page.wait_for_function("document.querySelector('#game-user-pane-third [data-withdrawn]').textContent==='375'")
    assert calls[-1]['ids']==[8]
    pane.locator('[data-action=cards]').click()
    pane.locator('[data-game-select="7"]').check()
    pane.locator('[data-page="2"]').first.click()
    page.wait_for_function("document.querySelector('#game-user-pane-third [data-game-select=\"2\"]')!==null")
    assert pane.locator('[data-game-batch=approve]').is_disabled()
    assert pane.locator('[data-game-review][data-review-id="1"]').count()==0

    pane.locator('[data-action=search]').click()
    pane.locator('[name=updated_range]').fill('2025-01-03 00:00:00 - 2025-01-03 23:59:59')
    page.locator('.game-user-dialog .daterangepicker:visible').wait_for()
    page.keyboard.press('Escape')
    with page.expect_response(lambda r:'/withdrawals?' in r.url and 'updated_from=' in r.url):
        pane.locator('[type=submit]').click()
    assert queries[-1]['updated_from']=='2025-01-02T16:00:00.000Z'
    assert 'created_from' not in queries[-1]
    pane.locator('tbody tr').first.wait_for()
    page.screenshot(path='visual-baseline/verified/game-withdrawals-dialog.png')
    pane.locator('[data-game-review=refuse][data-review-id="7"]').click()
    count=len(calls)
    page.evaluate("document.querySelector('.game-user-dialog').close()")
    page.locator('.withdrawal-confirm').wait_for(state='detached')
    assert len(calls)==count
    assert errors==[],errors
    browser.close()
    print('Game withdrawal summary, money units, single/batch reviews, reason validation, filters, cards, selection and cleanup passed')
