"""Verify actual list renderer against paginated fixture responses; no database writes."""
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import csv
import io
from playwright.sync_api import sync_playwright

rows=[dict(id=i,name=f'分页主体{i}',parent_id=0,status=1,created_at='2026-09-16T00:00:00Z') for i in range(1,36)]
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def respond(route):
        q=parse_qs(urlparse(route.request.url).query)
        data=[] if q.get('name') else sorted(rows,key=lambda r:r['id'],reverse=q.get('order',['desc'])[0]=='desc')
        start=int(q.get('offset',[0])[0]);size=int(q.get('limit',[10])[0])
        route.fulfill(json={'total':len(data),'items':data[start:start+size]})
    page.route('**/api/v1/agents?*',respond)
    page.goto('http://127.0.0.1:3000/#agents')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    page.wait_for_function("document.querySelectorAll('[data-agent-select]').length===10")
    assert page.locator('[data-agent-select]').first.get_attribute('data-agent-select')=='35'
    page.get_by_label('切换视图',exact=True).click()
    assert page.locator('.agent-card-table').count()==1
    assert page.locator('.agent-panel thead').is_hidden()
    page.get_by_label('切换视图',exact=True).click()
    assert page.locator('.agent-panel thead').is_visible()
    page.get_by_label('显示列',exact=True).click()
    page.locator('[data-agent-column="4"]').uncheck()
    assert page.locator('.agent-panel th').nth(4).is_hidden()
    page.get_by_label('显示列',exact=True).click()
    page.locator('#agentNext').click()
    page.wait_for_function("document.querySelector('[data-agent-select]')?.dataset.agentSelect==='25'")
    assert page.locator('.agent-panel th').nth(4).is_hidden()
    page.get_by_label('显示列',exact=True).click()
    page.locator('[data-agent-column="4"]').check()
    assert page.locator('.agent-panel th').nth(4).is_visible()
    page.get_by_label('显示列',exact=True).click()
    page.locator('#agentPageSize').select_option('20')
    page.wait_for_function("document.querySelectorAll('[data-agent-select]').length===20")
    page.locator('.agent-export summary').click()
    with page.expect_download() as download:
        page.locator('[data-agent-export=csv]').click()
    exported=list(csv.reader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))))
    assert len(exported)==36, len(exported)
    assert '操作' not in exported[0]
    page.locator('[data-agent-select]').first.check()
    page.get_by_label('显示列',exact=True).click()
    page.locator('[data-agent-column="4"]').uncheck()
    page.get_by_label('显示列',exact=True).click()
    page.locator('.agent-export summary').click()
    with page.expect_download() as download:
        page.locator('[data-agent-export=csv]').click()
    exported=list(csv.reader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))))
    assert len(exported)==2
    assert '状态' not in exported[0]
    page.locator('#agentNext').click()
    page.wait_for_function("document.querySelectorAll('[data-agent-select]').length===15")
    assert page.locator('#agentNext').is_disabled()
    page.locator('[data-agent-sort=id]').click()
    page.wait_for_function("document.querySelector('[data-agent-select]')?.dataset.agentSelect==='1'")
    page.locator('#agentSearchToggle').click()
    page.locator('#agentFilters [name=name]').fill('no match')
    page.locator('#agentFilters').evaluate('f=>f.requestSubmit()')
    page.wait_for_function("document.querySelector('#agentSelectAll')?.disabled")
    assert page.locator('.agent-panel .pagination').is_hidden()
    page.locator('#agentFilters [type=reset]').click()
    page.wait_for_function("document.querySelectorAll('[data-agent-select]').length===20")
    assert not errors,errors
    browser.close()
print('Agent pagination: page size, last page, sort reset, empty results and filter reset passed')
