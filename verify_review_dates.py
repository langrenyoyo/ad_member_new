"""Date picker interaction against local upstream assets, in a non-Beijing browser timezone."""
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(timezone_id='America/Los_Angeles')
    page.clock.set_fixed_time(datetime(2026,9,12,17,tzinfo=timezone.utc))
    page.route('http://127.0.0.1:3010/date-fixture',lambda route:route.fulfill(content_type='text/html',body='<form><input name="created_range"><input name="updated_range"></form><p id="reviewError"></p><button id="outside">Outside</button>'))
    page.goto('http://127.0.0.1:3010/date-fixture')
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_style_tag(url='/review-details.css')
    for name in ['review-export.js','review-dates.js']:
        page.add_script_tag(url='/'+name)
    page.evaluate("attachReviewDates(document.querySelector('form'))")
    field=page.locator('[name=created_range]')
    field.click()
    page.locator('.daterangepicker:visible .ranges li',has_text='今天').click()
    assert field.input_value()=='2026-09-13 00:00:00 - 2026-09-13 23:59:59'
    field.click()
    page.locator('.daterangepicker:visible .ranges li',has_text='最近7天').click()
    assert field.input_value()=='2026-09-07 00:00:00 - 2026-09-13 23:59:59'
    field.click()
    page.locator('.daterangepicker:visible .ranges li',has_text='上月').click()
    assert field.input_value()=='2026-08-01 00:00:00 - 2026-08-31 23:59:59'
    field.click()
    page.locator('.daterangepicker:visible .ranges li',has_text='自定义').click()
    assert page.locator('.daterangepicker:visible .calendar.left').is_visible()
    page.locator('.daterangepicker:visible .calendar.left td.available:not(.off)').filter(has_text='15').first.click()
    page.locator('.daterangepicker:visible .calendar.left td.available:not(.off)').filter(has_text='17').first.click()
    assert field.input_value()=='2026-08-15 00:00:00 - 2026-08-17 23:59:59'
    page.locator('[name=updated_range]').click()
    assert page.locator('[name=updated_range]').input_value()==''
    page.locator('.daterangepicker:visible .ranges li',has_text='昨天').click()
    assert page.locator('[name=updated_range]').input_value()=='2026-09-12 00:00:00 - 2026-09-12 23:59:59'
    field.fill('')
    page.mouse.click(1000,700)
    assert field.input_value()==''
    page.evaluate("document.querySelector('form').remove()")
    page.wait_for_function('reviewDateBindings.size===0')
    assert page.locator('.daterangepicker').count()==0
    assert not errors,errors
    browser.close()
    print('PASS: Beijing shortcuts in foreign timezone, custom calendar selection, independent fields, empty input, detached picker cleanup.')
