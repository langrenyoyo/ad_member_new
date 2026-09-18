"""Exercise generic game tables with fixture responses and real browser HTML parsing."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.route('http://fixture.test/**', lambda route: route.fulfill(body='<main id="panel"></main>', content_type='text/html'))
    page.goto('http://fixture.test/')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_script_tag(content="""
      const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
      const profileLogTime=String;
      const attachReviewDates=()=>{};
      window.calls=[];
      const api=async path=>{calls.push(path);const q=new URL(path,'http://fixture.test').searchParams;
        return q.get('username')?{total:0,items:[]}:{total:21,items:[{id:1,username:'fixture',status:1,network_status:0,is_white:1}]};};
    """)
    page.add_script_tag(path=str(Path('public/game-userdata.js').resolve()))
    page.evaluate("window.controller=mountGameUserTable(document.querySelector('#panel'),237,gameUserTabs[0]);controller.refresh()")
    page.locator('tbody tr').wait_for()
    page.get_by_label('每页记录数', exact=True).click()
    assert page.locator('[data-game-size]').all_text_contents() == ['10','15','20','25']
    page.locator('[data-game-size="20"]').click()
    page.wait_for_function("calls.at(-1).includes('limit=20')")
    page.get_by_label('下一页', exact=True).click()
    page.wait_for_function("calls.at(-1).includes('offset=20')")
    page.get_by_label('显示列', exact=True).click()
    page.locator('[data-column=ecpm]').uncheck()
    assert 'ECPM' not in page.locator('thead').inner_text()
    page.get_by_label('筛选', exact=True).click()
    page.locator('[name=username]').fill('missing')
    page.locator('[type=submit]').click()
    page.wait_for_function("document.querySelector('tbody').textContent.includes('没有找到匹配的记录')")
    assert page.locator('tbody td').count() == 1
    assert not errors, errors
    page.evaluate('controller.destroy()')
    browser.close()
print('Game table markup: page size, pagination, columns, filters and empty results passed')
