"""Window state parity using reference geometry and isolated browser records."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

reference=json.loads(Path('visual-baseline/fixtures/member-lottery/reference-window.json').read_text())
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    row={'id':9200,'username':'fixture','name':'fixture','raffle_num':12}
    errors=[];writes=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/api/auth/login',lambda r:r.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}}))
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    def detail(r):
        if r.request.method!='GET':writes.append(r.request.method)
        r.fulfill(json=row)
    page.route('**/api/v1/members/9200',detail)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.locator('[data-edit="9200"]').click()
    window=page.locator('#modal>.modal')
    window.wait_for(state='visible')
    assert window.bounding_box()==reference['normal']
    page.locator('[data-member-tab-button="lottery"]').click()
    page.fill('[name=raffle_num]','37')
    maximize=page.locator('[data-member-window=maximize]')
    minimize=page.locator('[data-member-window=minimize]')
    maximize.click();assert window.bounding_box()==reference['maximized']
    assert minimize.is_hidden()
    maximize.click();assert window.bounding_box()==reference['restored']
    minimize.click();assert window.bounding_box()==reference['minimized']
    assert page.locator('#editorForm').is_hidden()
    assert page.locator('[data-edit="9200"]').is_visible()
    maximize.click();assert window.bounding_box()==reference['restored_from_minimized']
    assert page.locator('[name=raffle_num]').input_value()=='37'
    assert page.locator('[data-member-tab-button=lottery]').get_attribute('aria-selected')=='true'
    page.mouse.move(800,262);page.mouse.down();page.mouse.move(900,312);page.mouse.up()
    moved=window.bounding_box();assert moved==dict(x=660,y=290,width=800,height=600),moved
    maximize.click();maximize.click();assert window.bounding_box()==moved
    minimize.click();maximize.click();assert window.bounding_box()==moved
    page.locator('#closeModal').click();page.locator('[data-edit="9200"]').click()
    window.wait_for(state='visible');assert window.bounding_box()==reference['normal']
    minimize.click();page.evaluate('location.hash="members?agent_id=6200"')
    page.locator('#modal').wait_for(state='hidden')
    assert not errors,errors
    assert not writes,writes
    browser.close()
print('Member window: reference maximize/minimize/restore geometry, draft retention, drag, reopening and navigation passed')
