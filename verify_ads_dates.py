"""Verify ad date selection and request boundaries in a foreign browser timezone."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(timezone_id='America/Los_Angeles',accept_downloads=True)
    page.clock.set_fixed_time(datetime(2026,9,17,17,tzinfo=timezone.utc))
    queries=[];exports=[]
    def listing(route):
        queries.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'total':0,'items':[],'summary':{}})
    def export(route):
        exports.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(content_type='text/csv',body='id\n')
    page.route('**/api/v1/ads?*',listing)
    page.route('**/api/v1/ads/export?*',export)
    page.goto('http://127.0.0.1:3000/#ads')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    field=page.locator('#watchedRange')
    expect(field).to_have_value('2026-09-18 00:00:00 - 2026-09-18 23:59:59')
    page.locator('.ads-empty').wait_for()
    assert queries[-1]['watched_from']==['2026-09-17T16:00:00.000Z']
    assert queries[-1]['watched_to']==['2026-09-18T15:59:59.000Z']
    field.click()
    page.locator('.daterangepicker:visible .ranges li',has_text='本月').click()
    expect(field).to_have_value('2026-09-01 00:00:00 - 2026-09-30 23:59:59')
    field.click()
    page.locator('.daterangepicker:visible .ranges li',has_text='自定义').click()
    calendar=page.locator('.daterangepicker:visible .calendar.left')
    calendar.locator('td.available:not(.off)').filter(has_text='15').first.click()
    calendar.locator('td.available:not(.off)').filter(has_text='17').first.click()
    expect(field).to_have_value('2026-09-15 00:00:00 - 2026-09-17 23:59:59')
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=submit]').click()
    assert queries[-1]['watched_from']==['2026-09-14T16:00:00.000Z']
    assert queries[-1]['watched_to']==['2026-09-17T15:59:59.000Z']
    expected_dates={key:queries[-1][key] for key in ('watched_from','watched_to')}
    page.locator('#adsExportToggle').click()
    with page.expect_download():
        page.locator('[data-ads-export=csv]').click()
    assert all(queries[-1][key]==value for key,value in expected_dates.items())
    assert queries[-1]['offset']==['0'] and queries[-1]['limit']==['200']
    with page.expect_download():
        page.evaluate('downloadAds()')
    assert all(exports[-1][key]==queries[-1][key] for key in ('watched_from','watched_to'))
    with page.expect_response(lambda r:'/api/v1/ads?' in r.url):
        page.locator('#adsFilters [type=reset]').click()
    expect(field).to_have_value('2026-09-18 00:00:00 - 2026-09-18 23:59:59')
    field.click()
    page.locator('.daterangepicker:visible').wait_for()
    page.evaluate("location.hash='dashboard'")
    page.wait_for_function('reviewDateBindings.size===0')
    assert page.locator('.daterangepicker').count()==0
    browser.close()
print('PASS: Beijing defaults, whole-month shortcut, custom dates, UTC list/export bounds, reset and picker cleanup')
