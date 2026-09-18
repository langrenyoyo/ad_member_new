"""Recipient blacklist interactions with in-memory API responses only."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    rows=[{'id':9000+i,'receive_name':'fixture '+str(i),'receive_tel':'001234'+str(i),'status':1-i%2,
           'created_at':'2026-09-18T00:00:00Z','updated_at':'2026-09-18T00:00:00Z'} for i in range(25)]
    rows[0]['receive_name']='fixture 0 <>&'
    withdrawals=[{'id':42,'user_id':42,'game_id':237,'status':0,'receive_name':'recipient <>&','receive_tel':'00123','exchange_value':10}]
    writes=[];reads=[];held=[];errors=[];state={'fail':False,'defer':False,'read_fail':False}
    page.on('pageerror',lambda error:errors.append(str(error)))
    def fixture(route):
        url=urlparse(route.request.url);path=url.path.split('/api/')[-1].removeprefix('v1/');query=parse_qs(url.query)
        if path=='auth/login':route.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}});return
        if route.request.method!='GET':
            body=json.loads(route.request.post_data);writes.append((path,body))
            if state['defer']:held.append(route);return
            if state['fail']:route.fulfill(status=403,json={'detail':'fixture permission denied'});return
            if path=='withdrawals/42/blacklist':route.fulfill(json={'id':9100,'status':1});return
            assert path.startswith('withdrawal-blacklist/') and route.request.method=='PATCH'
            row=next(r for r in rows if r['id']==int(path.split('/')[-1]));row['status']=body['status'];route.fulfill(json=row);return
        if path=='withdrawal-blacklist':
            reads.append(query)
            if state['read_fail']:route.fulfill(status=503,json={'detail':'fixture unavailable'});return
            items=list(rows)
            for key in ['receive_name','receive_tel','status']:
                if key in query:items=[r for r in items if str(r[key])==query[key][0]]
            items.sort(key=lambda r:r[query.get('sort',['id'])[0]],reverse=query.get('order',['desc'])[0]=='desc')
            offset=int(query.get('offset',[0])[0]);limit=int(query.get('limit',[20])[0])
            route.fulfill(json={'items':items[offset:offset+limit],'total':len(items)});return
        route.fulfill(json={'items':withdrawals,'total':1,'summary':{}} if path=='withdrawals' else {'items':[],'total':0})
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:3000/#withdrawals')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    block=page.locator('[data-withdrawal-blacklist="42"]')
    block.click();page.locator('.withdrawal-confirm footer [value=cancel]').click()
    assert not writes
    state['fail']=True
    block.click();page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_function("document.querySelector('#reviewError').textContent.includes('permission denied')")
    assert block.is_enabled()
    state['fail']=False;writes.clear()
    block.click();page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_timeout(100)
    assert writes==[('withdrawals/42/blacklist',{'receive_name':'recipient <>&','receive_tel':'00123'})]
    page.locator('#withdrawalBlacklist').click()
    dialog=page.locator('.withdrawal-blacklist-dialog');dialog.locator('tbody tr').first.wait_for()
    assert dialog.bounding_box()['width']==800 and dialog.bounding_box()['height']==600
    assert dialog.locator('.ads-filters').is_visible()
    assert dialog.locator('tbody tr').count()==10
    assert dialog.locator('[data-blacklist-toggle]').first.get_attribute('aria-checked')=='true'
    assert dialog.locator('th:visible').count()==6
    dialog.locator('[data-search-field=receive_tel]').first.click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog tbody').rows.length===1")
    assert reads[-1]['receive_tel']==['00123424']
    dialog.locator('[type=reset]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog tbody').rows.length===10")
    dialog.locator('[aria-label=下一页]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog tbody tr td[data-field=id]').textContent==='9014'")
    assert reads[-1]['offset']==['10']
    dialog.locator('[data-sort=id]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog tbody tr td[data-field=id]').textContent==='9000'")
    dialog.locator('[name=status]').select_option('1');dialog.locator('form').evaluate('form=>form.requestSubmit()')
    page.wait_for_timeout(100);assert reads[-1]['status']==['1']
    state['fail']=True
    dialog.locator('[data-blacklist-toggle="9000"]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog [role=alert]').textContent.includes('permission denied')")
    assert dialog.locator('[data-blacklist-toggle="9000"]').get_attribute('aria-checked')=='true'
    state['fail']=False
    dialog.locator('[data-blacklist-toggle="9000"]').click()
    dialog.locator('[data-blacklist-toggle="9000"]').wait_for(state='detached')
    assert rows[0]['status']==0
    dialog.locator('[type=reset]').click()
    dialog.locator('[data-blacklist-select="9000"]').wait_for()
    dialog.locator('[data-blacklist-select="9000"]').check()
    dialog.locator('[data-action=cards]').click()
    assert dialog.locator('[data-blacklist-select="9000"]').is_checked()
    dialog.locator('[data-action=cards]').click()
    dialog.locator('.game-user-export summary').click()
    with page.expect_download() as download_info:dialog.locator('[data-export=csv]').click()
    downloaded=Path(download_info.value.path()).read_text(encoding='utf-8-sig')
    assert 'fixture 0' in downloaded and 'fixture 1' not in downloaded and '禁用' in downloaded
    assert '<button' not in downloaded and '9000' in downloaded
    for kind in ['json','xml','txt','doc','excel']:
        dialog.locator('.game-user-export summary').click()
        with page.expect_download() as export_info:dialog.locator('[data-export='+kind+']').click()
        content=Path(export_info.value.path()).read_bytes()
        assert b'fixture 0' in content and b'fixture 1' not in content,kind
        assert b'<button' not in content,kind
        if kind=='xml':assert 'fixture 0 <>&' in ''.join(ET.fromstring(content).itertext())
    dialog.locator('[data-blacklist-all]').check()
    assert dialog.locator('[data-blacklist-select]').evaluate_all('els=>els.every(el=>el.checked)')
    dialog.locator('.game-user-columns summary').click();dialog.locator('[data-column=updated_at]').check()
    assert dialog.locator('th[data-field=updated_at]').is_visible()
    page.keyboard.press('Escape');assert dialog.is_visible()
    # Window state and drag retain the current table/filter state.
    dialog.locator('[data-blacklist-minimize]').click()
    assert not dialog.evaluate('el=>el.matches(":modal")')
    dialog.locator('[data-blacklist-maximize]').click()
    assert dialog.evaluate('el=>el.matches(":modal")')
    dialog.locator('[data-blacklist-maximize]').click()
    assert dialog.bounding_box()['width']==1920
    dialog.locator('[data-blacklist-maximize]').click()
    header=dialog.locator('header span').bounding_box();before=dialog.bounding_box()
    page.mouse.move(header['x']+40,header['y']+10);page.mouse.down();page.mouse.move(header['x']+80,header['y']+30);page.mouse.up()
    assert dialog.bounding_box()['x']>before['x']
    state['read_fail']=True;dialog.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog [role=alert]').textContent==='fixture unavailable'")
    assert dialog.locator('tbody tr').count()==10
    state['read_fail']=False;dialog.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog [role=alert]').textContent===''")
    # A stale mutation does not overwrite newly filtered data.
    state['defer']=True;dialog.locator('[data-blacklist-toggle="9000"]').click()
    page.wait_for_timeout(100);assert len(held)==1
    dialog.locator('[name=receive_name]').fill('fixture 2');dialog.locator('form').evaluate('f=>f.requestSubmit()')
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog tbody').rows.length===1")
    count=len(reads);held.pop().fulfill(status=403,json={'detail':'stale failure'})
    page.wait_for_timeout(100)
    assert len(reads)==count and 'stale failure' not in dialog.inner_text()
    state['defer']=False
    dialog.locator('[type=reset]').click();page.wait_for_timeout(100)
    page.set_viewport_size({'width':390,'height':844});dialog.evaluate('el=>{el.style.transform="";}')
    assert dialog.locator('main').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.screenshot(path='visual-baseline/verified/withdrawal-blacklist-mobile.png')
    # All mode gathers more than one server page and keeps the selection table usable.
    page.set_viewport_size({'width':1920,'height':1080})
    rows.extend({'id':9000+i,'receive_name':'fixture '+str(i),'receive_tel':'001234'+str(i),'status':1,
                 'created_at':'2026-09-18T00:00:00Z','updated_at':'2026-09-18T00:00:00Z'} for i in range(25,225))
    dialog.locator('[data-action=refresh]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog .game-page-info').textContent.includes('225')")
    dialog.locator('.game-page-size summary').click();dialog.locator('[data-game-size=All]').click()
    page.wait_for_function("document.querySelector('.withdrawal-blacklist-dialog tbody').rows.length===225")
    assert reads[-2]['limit']==['200'] and reads[-1]['offset']==['200']
    # Closing a window with an outstanding toggle must not inject its response into a new window.
    state['defer']=True;dialog.locator('[data-blacklist-toggle="9000"]').click()
    page.wait_for_timeout(100);assert len(held)==1
    dialog.locator('[data-blacklist-close]').click();dialog.wait_for(state='detached')
    page.locator('#withdrawalBlacklist').click();dialog.locator('tbody tr').first.wait_for()
    count=len(reads);held.pop().fulfill(status=403,json={'detail':'closed window failure'})
    page.wait_for_timeout(100)
    assert len(reads)==count and 'closed window failure' not in dialog.inner_text()
    state['defer']=False
    page.evaluate("location.hash='members'");dialog.wait_for(state='detached')
    # Leaving the source page cancels confirmation, and ignores a submitted request's late failure.
    page.evaluate("location.hash='withdrawals'");block.wait_for()
    block.click();page.locator('.withdrawal-confirm').wait_for()
    count=len(writes);page.evaluate("location.hash='members'")
    page.locator('.withdrawal-confirm').wait_for(state='detached');assert len(writes)==count
    page.evaluate("location.hash='withdrawals'");block.wait_for()
    state['defer']=True;block.click();page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_timeout(100);assert len(held)==1
    page.evaluate("location.hash='members'");block.wait_for(state='detached')
    held.pop().fulfill(status=409,json={'detail':'old source conflict'})
    page.wait_for_timeout(100)
    assert 'old source conflict' not in page.locator('body').inner_text()
    assert page.evaluate('location.hash')=='#members'
    assert not errors,errors
    browser.close()
print('Blacklist browser: block, exact filters, sorting/paging, toggle retry, selected export, windows, stale isolation and mobile passed')
