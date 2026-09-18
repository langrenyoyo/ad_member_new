"""Batch transfer UI uses isolated responses; no business writes or real payments."""
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    errors=[];writes=[];held=[];reads=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    state={'mode':'unavailable'}
    rows=[{'id':7101+i,'user_id':42+i,'username':'fixture','status':1,'plan_status':0,
           'exchange_value':125,'game_id':237,'created_at':'2026-09-18T00:00:00Z'} for i in range(2)]
    def fixture(route):
        path=route.request.url.split('/api/')[-1].removeprefix('v1/')
        if path=='auth/login':
            route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        if route.request.method=='GET':
            reads.append(path)
            route.fulfill(json={'items':rows,'total':len(rows),'summary':{'withdrawn':9990,'pending':0,'blacklisted':None}} if path.startswith('withdrawals?') else {'items':[],'total':0});return
        assert path=='withdrawals/batch-transfer',path
        writes.append(json.loads(route.request.post_data))
        if state['mode']=='defer':held.append(route);return
        if state['mode']=='unavailable':route.fulfill(status=503,json={'detail':'支付渠道尚未接通，未执行转账，提现记录保持原状态'});return
        if state['mode']=='forbidden':route.fulfill(status=403,json={'detail':'fixture permission denied'});return
        for row in rows:row['plan_status']=1
        route.fulfill(json={'updated':2,'payment_confirmed':False})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('form=>form.requestSubmit()')
    transfer=page.locator('#withdrawalBatchTransfer')
    transfer.wait_for()
    assert transfer.is_disabled()
    assert page.locator('[data-withdrawal-summary=withdrawn]').inner_text()=='已提现：999元'
    assert page.locator('[data-withdrawal-summary=pending]').inner_text()=='提现中：0元'
    assert page.locator('[data-withdrawal-summary=blacklisted]').inner_text()=='拉黑已提现：-'
    page.locator('#withdrawalSelectAll').check()
    transfer.click()
    assert page.locator('.withdrawal-confirm-message').inner_text()=='确认批量支付宝转账(实时)吗'
    assert page.locator('[data-withdrawal-select]').evaluate_all('els=>els.every(el=>el.disabled)')
    assert transfer.is_disabled() and page.locator('#withdrawalBatchRefuse').is_disabled()
    page.locator('.withdrawal-confirm footer [value=cancel]').click()
    page.locator('.withdrawal-confirm').wait_for(state='detached')
    assert not writes and page.locator('#withdrawalSelectAll').is_checked()
    for mode,message in [('unavailable','支付渠道尚未接通'),('forbidden','fixture permission denied')]:
        state['mode']=mode
        transfer.click();page.locator('.withdrawal-confirm-ok').click()
        page.wait_for_function('(message)=>document.querySelector("#reviewError").textContent.includes(message)',arg=message)
        assert page.locator('[data-withdrawal-select]').evaluate_all('els=>els.every(el=>el.checked&&!el.disabled)')
        assert page.locator('[data-review-cell=plan_status]').evaluate_all("els=>els.every(el=>el.textContent.includes('默认'))")
    assert writes==[{'ids':[7101,7102]},{'ids':[7101,7102]}]
    state['mode']='defer'
    transfer.click();page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_timeout(100)
    assert len(held)==1 and transfer.is_disabled()
    transfer.evaluate('el=>el.click()')
    assert len(writes)==3
    held.pop().fulfill(json={'updated':2,'payment_confirmed':False})
    page.wait_for_function('document.querySelector("#withdrawalBatchTransfer").disabled && !document.querySelector("#withdrawalSelectAll").checked')
    assert not page.locator('#reviewError').inner_text()
    # An old successful mutation must not refresh a newer filter/state generation.
    page.locator('#withdrawalSelectAll').check();transfer.click();page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_timeout(100);assert len(held)==1
    page.locator('#reviewRefresh').click()
    page.wait_for_function('!document.querySelector("#withdrawalSelectAll").checked')
    before=len(reads)
    held.pop().fulfill(json={'updated':2,'payment_confirmed':False})
    page.wait_for_timeout(150)
    assert len(reads)==before
    # Navigation cancels an unsubmitted confirmation and isolates an in-flight result.
    page.locator('#withdrawalSelectAll').check();transfer.click()
    page.evaluate("location.hash='members'")
    page.locator('.withdrawal-confirm').wait_for(state='detached')
    assert len(writes)==4
    page.evaluate("location.hash='withdrawals'");transfer.wait_for()
    page.locator('#withdrawalSelectAll').check();transfer.click();page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_timeout(100);assert len(held)==1
    page.evaluate("location.hash='members'")
    page.locator('.member-filters').wait_for()
    before=len(reads)
    held.pop().fulfill(status=503,json={'detail':'late transfer error'})
    page.wait_for_timeout(150)
    assert len(reads)==before and 'late transfer error' not in page.locator('#content').inner_text()
    page.evaluate("location.hash='withdrawals'");transfer.wait_for()
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#reviewSearchToggle').click()
    assert page.locator('.withdrawal-toolbar').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path='visual-baseline/verified/withdrawal-transfer-mobile.png')
    assert not errors,errors
    browser.close()
print('Withdrawal transfer: summaries, confirmation/cancel, locked selection, 503/403 retry, duplicate prevention, stale results and mobile passed')
