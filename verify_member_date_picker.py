"""Date selector selection, draft, reset and changed-only submission."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});writes=[];errors=[]
    row={'id':9200,'username':'fixture','game_addiction_time':'2026-09-17 12:34:56'}
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/api/auth/login',lambda r:r.fulfill(json={'access_token':'fixture','user':{'username':'fixture'}}))
    page.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    def detail(r):
        if r.request.method=='PATCH':writes.append(r.request.post_data_json)
        r.fulfill(json=row)
    page.route('**/api/v1/members/9200',detail)
    page.goto('http://127.0.0.1:3000/#members')
    page.fill('#loginForm [name=username]','fixture');page.fill('#loginForm [name=password]','fixture')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()');page.locator('[data-edit="9200"]').click()
    field=page.locator('[name=game_addiction_time]');field.click()
    widget=page.locator('.bootstrap-datetimepicker-widget');widget.wait_for(state='visible')
    assert '2026' in widget.inner_text()
    widget.locator('.day:not(.old):not(.new)').filter(has_text='18').click()
    assert field.input_value()=='2026-09-18 12:34:56'
    widget.locator('[data-action=togglePicker]').click()
    widget.locator('[data-action=showHours]').click()
    widget.locator('[data-action=selectHour]').filter(has_text='23').click()
    widget.locator('[data-action=showMinutes]').click()
    widget.locator('[data-action=selectMinute]').filter(has_text='45').click()
    widget.locator('[data-action=showSeconds]').click()
    widget.locator('[data-action=selectSecond]').filter(has_text='50').click()
    assert field.input_value()=='2026-09-18 23:45:50'
    widget.locator('[data-action=incrementSeconds]').click()
    assert field.input_value()=='2026-09-18 23:45:51'
    widget.locator('[data-action=close]').click();assert widget.count()==0
    field.click();widget.wait_for(state='visible')
    page.locator('[data-member-tab-button=agent]').click();assert widget.count()==0
    page.locator('[data-member-tab-button=basic]').click();assert field.input_value()=='2026-09-18 23:45:51'
    page.locator('#editorForm [type=reset]').click()
    page.wait_for_function("jQuery('[name=game_addiction_time]').data('DateTimePicker').date().format('YYYY-MM-DD HH:mm:ss')==='2026-09-17 12:34:56'")
    field.fill('2026-10-01 08:09:10');field.press('Tab')
    page.locator('#editorForm [type=submit]').click();page.locator('#modal').wait_for(state='hidden')
    assert writes==[{'game_addiction_time':'2026-10-01 08:09:10'}],writes
    page.locator('[data-edit="9200"]').click()
    field.fill('');field.press('Tab')
    page.locator('#editorForm [type=submit]').click();page.locator('#modal').wait_for(state='hidden')
    assert writes[-1]=={'game_addiction_time':''},writes
    page.locator('[data-edit="9200"]').click();field.click();widget.wait_for(state='visible')
    page.locator('#closeModal').click();assert widget.count()==0
    assert not errors,errors
    browser.close()
print('Date picker: selection, time preservation, tabs, reset cache, typed date save and close cleanup passed')
