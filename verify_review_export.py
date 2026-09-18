"""Exercise six export formats and all/selected scope with isolated data."""
import csv
import io
import json
import tempfile
from pathlib import Path
from xml.etree import ElementTree
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as temporary, sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(accept_downloads=True)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('http://127.0.0.1:3010/export-fixture',lambda route:route.fulfill(content_type='text/html',body='<main id="content"></main>'))
    page.goto('http://127.0.0.1:3010/export-fixture')
    page.evaluate('''() => {
     window.$=selector=>document.querySelector(selector);
     window.esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
     window.state={view:'withdrawals'};window.profileLogTime=value=>value||'';window.adsOptions=async()=>[];
     window.requests=[];
     window.rows=Array.from({length:205},(_,i)=>({id:i+1,status:0,user_id:9,good_name:'ROW-'+(i+1)+' 中文 & <商品>',exchange_value:125,receive_tel:'00123',sub_msg:'a,"b"\\nc'}));
     window.api=async url=>{requests.push(url);const q=new URL(url,location.origin).searchParams;return {items:rows.slice(Number(q.get('offset')),Number(q.get('offset'))+Number(q.get('limit'))),total:rows.length};};
    }''')
    for name in ['review-details.css']:
        page.add_style_tag(url='/'+name)
    page.route('**/api/v1/member-filter-options/**',lambda route:route.fulfill(json={'total':0,'items':[]}))
    for name in ['vendor/jquery.min.js','vendor/selectpage.js','member-lookups.js','review-filters.js','withdrawal-actions.js','review-export.js','review-dates.js','withdrawals.js','subsidies.js']:
        page.add_script_tag(url='/'+name)
    page.evaluate('window.$ = selector => document.querySelector(selector)')
    page.evaluate("reviewStates.withdrawals.filters={username:'fixture-filter'};renderReviewPage('withdrawals')")
    assert page.locator('#reviewPageSizeMenu summary').inner_text().strip()=='10'
    page.locator('#reviewPageSizeMenu summary').click()
    page.locator('[data-review-size="50"]').click()
    page.wait_for_function("requests.at(-1).includes('limit=50')")
    page.locator('[data-review-page="5"]').click()
    page.wait_for_function("requests.at(-1).includes('offset=200')")
    assert page.locator('tbody tr').count()==5
    assert page.locator('#reviewNext').is_enabled()
    page.locator('#reviewPrev').click()
    page.wait_for_function("requests.at(-1).includes('offset=150')")
    assert page.locator('tbody tr').count()==50
    page.locator('#reviewPageSizeMenu summary').click()
    page.locator('[data-review-size="10"]').click()
    page.wait_for_function("requests.at(-1).includes('offset=0') && requests.at(-1).includes('limit=10')")
    assert page.locator('#reviewPrev').is_enabled()
    assert page.evaluate("localStorage.getItem('pagesize')")=='10'
    # Lazy jQuery loading must not replace the application's global $ helper.
    page.evaluate('loadReviewExporter()')
    assert page.evaluate("$('#content') instanceof HTMLElement")
    def download(kind):
        page.locator('.review-export summary').click()
        with page.expect_download() as event:
            page.locator(f'[data-review-export="{kind}"]').click()
        item=event.value
        target=Path(temporary)/item.suggested_filename
        item.save_as(target)
        return item.suggested_filename,target.read_text(encoding='utf-8-sig')
    _,content=download('csv')
    data=list(csv.reader(io.StringIO(content)))
    assert len(data)==206,len(data)
    assert data[-1][0]=='205'
    assert 'ROW-205' in content
    assert page.evaluate("requests.some(url=>url.includes('offset=200'))")
    assert page.evaluate("requests.every(url=>url.includes('username=fixture-filter') && url.includes('sort=id') && url.includes('order=desc'))")
    page.locator('[data-withdrawal-select="2"]').check()
    page.locator('[data-withdrawal-select="4"]').check()
    before=page.evaluate('requests.length')
    for kind,extension in [('json','.json'),('xml','.xml'),('csv','.csv'),('txt','.txt'),('doc','.doc'),('excel','.xls')]:
        name,content=download(kind)
        assert name.endswith(extension),name
        assert 'ROW-2' in content and 'ROW-4' in content
        assert 'ROW-1' not in content and 'ROW-205' not in content
        if kind=='json':
            payload=json.loads(content)
            assert set(payload)=={'header','data'}
            assert len(payload['data'])==2
        if kind=='xml':
            parsed=ElementTree.fromstring(content)
            assert len(parsed.findall('./data/row'))==2
            assert any(node.text=='ROW-2 中文 & <商品>' for node in parsed.findall('./data/row/*'))
        if kind=='csv':
            selected=list(csv.reader(io.StringIO(content)))
            assert len(selected)==3
            assert '\u64cd\u4f5c' not in selected[0]
            assert selected[1][selected[0].index('\u91d1\u989d')]=='12.5\u5143'
        if kind in ['doc','excel']:assert '<table' in content.lower()
    assert page.evaluate('requests.length')==before
    page.locator('.withdrawal-columns summary').click()
    page.locator('[data-withdrawal-column="receive_tel"]').uncheck()
    page.keyboard.press('Escape')
    _,content=download('csv')
    assert '\u8054\u7cfb\u65b9\u5f0f' not in next(csv.reader(io.StringIO(content)))
    page.locator('[data-review-page="21"]').click()
    page.wait_for_function("requests.at(-1).includes('offset=200')")
    page.evaluate('rows=rows.slice(0,3)')
    page.locator('#reviewRefresh').click()
    page.wait_for_function("document.querySelector('[data-review-page=\"1\"]')?.getAttribute('aria-current')==='page'")
    assert page.locator('tbody tr').count()==3
    assert page.locator('#reviewNext').is_hidden()
    page.evaluate("state.view='subsidies';renderReviewPage('subsidies')")
    page.locator('[data-subsidy-select="3"]').check()
    _,content=download('csv')
    data=list(csv.reader(io.StringIO(content)))
    assert len(data)==2 and data[1][0]=='3'
    # Leaving a page while its export request is pending must not download old data.
    page.locator('[data-subsidy-select="3"]').uncheck()
    downloads=[];page.on('download',lambda item:downloads.append(item))
    page.evaluate("window.exportMenu=document.querySelector('.review-export');window.api=()=>new Promise(resolve=>{window.releaseExport=()=>resolve({total:rows.length,items:rows});});void 0")
    page.locator('.review-export summary').click()
    page.locator('[data-review-export=csv]').click()
    page.wait_for_function("typeof releaseExport==='function'")
    page.evaluate("document.querySelector('.withdrawal-panel').remove();releaseExport()")
    page.wait_for_function("!exportMenu.hasAttribute('aria-busy')")
    assert not downloads
    assert page.locator('.review-export-table').count()==0
    assert not errors,errors
    browser.close()
    print('PASS: all 205 filtered rows, selected-only six formats, amount display, excluded actions, independent application $ helper.')
