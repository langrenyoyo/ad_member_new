"""Exercise real review UI scripts with isolated responses; never mutate business data."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.route('http://review-fixture.test/', lambda route: route.fulfill(content_type='text/html', body='<main id="content"></main>'))
    page.goto('http://review-fixture.test/')
    page.route('http://review-fixture.test/vendor/*',lambda route:route.fulfill(path=str(ROOT/'public/vendor'/route.request.url.rsplit('/',1)[-1])))
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.evaluate('''() => {
      window.$ = selector => document.querySelector(selector);
      window.esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      window.profileLogTime = value => value || '';
      window.state = {view:'subsidies'};
      window.adsOptions = async () => [];
      window.calls = [];
      window.readCalls = [];
      window.api = async (url, options) => {
        if(options) { calls.push({url, body:JSON.parse(options.body)}); return {}; }
        readCalls.push(url);
        return {items:[{id:7,user_id:12,status:0,exchange_value:125,exchange_type:1,plan_status:0,vip:2,good_name:'fixture product',device_manufacturer:'fixture phone',check_status_txt:'review supplied',sub_msg:'gateway message',reason:'review reason',delivery_name:'Courier',delivery_no:'00123',remark:'<b>source note</b>',is_true:1,pics:['https://fixture.test/proof.svg','javascript:alert(1)']}],total:1,permissions:{edit:true,review:true,row_review:true,transfer:true,blacklist:true}};
      };
    }''')
    page.route('https://fixture.test/**', lambda route: route.fulfill(
        content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="green"/></svg>'))
    for name in ['vendor/bootstrap.min.css', 'vendor/selectpage.css', 'ads.css', 'withdrawals.css', 'review-details.css']:
        page.add_style_tag(path=str(ROOT / 'public' / name))
    page.route('**/api/v1/member-filter-options/**',lambda route:route.fulfill(json={'total':0,'items':[]}))
    for name in ['vendor/jquery.min.js','vendor/selectpage.js','member-lookups.js','review-filters.js', 'withdrawal-actions.js', 'review-export.js','review-dates.js', 'withdrawals.js', 'subsidies.js']:
        page.add_script_tag(path=str(ROOT / 'public' / name))
    page.evaluate('window.$ = selector => document.querySelector(selector)')
    page.evaluate("renderReviewPage('subsidies')")
    assert page.locator('.subsidy-picture').count() == 1
    page.wait_for_function("document.querySelector('.subsidy-picture img').naturalWidth === 40")
    for value in ['https://fixture.test/a.svg,https://fixture.test/b.svg', '["https://fixture.test/a.svg","https://fixture.test/b.svg"]']:
        assert page.evaluate('(value) => {const el=document.createElement("div");el.innerHTML=subsidyPictures(value);return el.querySelectorAll("img").length}', value) == 2
    page.screenshot(path=str(ROOT / 'visual-baseline' / 'verified' / 'review-regression-fixture.png'), full_page=True)
    page.locator('#reviewViewToggle').click()
    assert page.locator('#reviewViewToggle').get_attribute('aria-pressed') == 'true'
    assert page.locator('thead').is_hidden()
    assert page.locator('[data-review-cell="parent_name"]').is_hidden()
    assert page.locator('[data-review-cell="tx_price"] .review-card-title').is_hidden()
    assert page.locator('[data-review-cell="sub_msg"] .review-card-title').is_visible()
    page.locator('[data-subsidy-select="7"]').check()
    assert page.locator('[data-subsidy-select="7"]').is_checked()
    page.locator('.subsidy-picture').click()
    page.locator('.subsidy-gallery img').wait_for(state='visible')
    page.keyboard.press('Escape')
    page.locator('.subsidy-gallery').wait_for(state='detached')
    page.screenshot(path=str(ROOT / 'visual-baseline' / 'verified' / 'subsidy-card-fixture.png'), full_page=True)
    page.locator('#reviewViewToggle').click()
    assert page.locator('thead').is_visible()
    assert page.locator('[data-subsidy-select="7"]').is_checked()
    assert page.locator('[data-review-action]').count() == 0
    assert page.locator('[data-subsidy-edit="7"]').count() == 1
    assert page.locator('[data-subsidy-delete="7"]').count() == 1
    page.locator('[data-withdrawal-sort="price"]').click()
    page.wait_for_function("readCalls.at(-1).includes('sort=price')")
    page.fill('[name=receive_name]', 'recipient fixture')
    page.fill('[name=receive_tel]', '00123')
    page.locator('#reviewFilters [type=submit]').click()
    page.wait_for_function("readCalls.at(-1).includes('receive_tel=00123')")
    assert page.locator('[name=receive_name]').input_value() == 'recipient fixture'
    page.locator('#subsidySelectAll').check()
    page.locator('[data-subsidy-batch="reject"]').click()
    page.locator('.withdrawal-confirm footer [value=cancel]').click()
    assert page.evaluate('calls.length') == 0
    page.locator('[data-subsidy-batch="reject"]').click()
    page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_function('calls.length === 1')
    assert page.evaluate('calls.pop()') == {'url':'/subsidies/batch-refuse','body':{'ids':[7]}}
    page.evaluate("state.view='withdrawals';renderReviewPage('withdrawals')")
    page.locator('#reviewViewToggle').click()
    assert page.locator('[data-review-cell="exchange_value"] .review-card-value').inner_text() == '12.5\u5143'
    page.locator('#reviewRefresh').click()
    page.wait_for_function("document.querySelector('#reviewViewToggle').getAttribute('aria-pressed') === 'true'")
    assert page.locator('thead').is_hidden()
    page.locator('#reviewViewToggle').click()
    for field, text in [('exchange_value','12.5\u5143'), ('vip','V2'), ('good_name','fixture product'), ('device_manufacturer','fixture phone'), ('check_status_txt','review supplied'), ('sub_msg','gateway message'), ('exchange_type','\u652f\u4ed8\u5b9d'), ('plan_status','\u9ed8\u8ba4')]:
        assert page.locator(f'[data-review-cell="{field}"]').inner_text() == text, field
    page.fill('[name=good_name]', 'fixture product')
    page.select_option('#reviewFilters [name=status]', '4')
    page.locator('#reviewFilters [type=submit]').click()
    page.wait_for_function("reviewStates.withdrawals.status === '4'")
    assert page.locator('[data-review-status="4"]').get_attribute('class') == 'active'
    page.locator('[data-review-status="0"]').click()
    page.wait_for_function("document.querySelector('#reviewFilters [name=status]').value === '0'")
    assert page.locator('[name=good_name]').input_value() == 'fixture product'
    page.once('dialog', lambda dialog: dialog.accept('withdrawal reason'))
    page.locator('[data-review-action="reject"]').click()
    page.wait_for_function('calls.length === 1')
    assert page.evaluate('calls[0]') == {'url':'/withdrawals/7/reject', 'body':{'reason':'withdrawal reason'}}
    # Ordinary refusal has a confirmation dialog, and sends no invented reason.
    page.locator('[data-review-action="refuse"]').click()
    page.locator('.withdrawal-confirm footer [value=cancel]').click()
    assert page.evaluate('calls.length') == 1
    page.locator('[data-review-action="refuse"]').click()
    page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_function('calls.length === 2')
    assert page.evaluate('calls[1]') == {'url':'/withdrawals/7/refuse','body':{}}
    assert page.locator('#withdrawalBatchRefuse').is_disabled()
    page.locator('[data-withdrawal-sort="exchange_value"]').click()
    page.wait_for_function("readCalls.at(-1).includes('sort=exchange_value') && readCalls.at(-1).includes('order=asc')")
    assert page.locator('[data-review-column="exchange_value"]').get_attribute('aria-sort') == 'ascending'
    page.locator('[data-withdrawal-sort="exchange_value"]').click()
    page.wait_for_function("readCalls.at(-1).includes('order=desc')")
    assert page.locator('[data-review-column="exchange_value"]').get_attribute('aria-sort') == 'descending'
    page.locator('#withdrawalSelectAll').check()
    assert page.locator('[data-withdrawal-select="7"]').is_checked()
    page.locator('#withdrawalBatchRefuse').click()
    page.locator('.withdrawal-confirm footer [value=cancel]').click()
    assert page.evaluate('calls.length') == 2
    page.locator('#withdrawalBatchRefuse').click()
    page.locator('.withdrawal-confirm-ok').click()
    page.wait_for_function('calls.length === 3')
    assert page.evaluate('calls[2]') == {'url':'/withdrawals/batch-refuse','body':{'ids':[7]}}
    assert page.locator('#withdrawalBatchRefuse').is_disabled()
    # Invalid filters must remain editable instead of destroying the form.
    page.fill('[name=created_range]', 'invalid date')
    page.locator('[name=created_range]').press('Escape')
    page.locator('#reviewFilters [type=submit]').click()
    assert page.locator('[name=created_range]').input_value() == 'invalid date'
    assert page.locator('#reviewError').inner_text()
    page.locator('#reviewFilters [type=reset]').click()
    page.wait_for_function("document.querySelector('[name=created_range]').value !== 'invalid date'")
    # An older failed request must not overwrite a more recent successful result.
    page.evaluate('''() => {
      window.originalApi=api;
      window.api=() => new Promise((resolve,reject) => {window.failOld=reject});
      window.oldRender=renderReviewPage('withdrawals');
    }''')
    page.evaluate("api=originalApi;renderReviewPage('withdrawals')")
    page.evaluate("failOld(new Error('stale error'));oldRender")
    assert page.locator('#reviewFilters').count() == 1
    assert 'stale error' not in page.locator('#content').inner_text()
    # Hidden columns are opt-in and survive a server refresh, paging and filters.
    assert page.locator('[data-review-column="reason"]').is_hidden()
    page.locator('.withdrawal-columns summary').click()
    for key, expected in [('delivery_name','Courier'), ('delivery_no','00123'), ('remark','<b>source note</b>'), ('is_true','\u662f')]:
        assert page.locator(f'[data-review-cell="{key}"]').is_hidden()
        page.locator(f'[data-withdrawal-column="{key}"]').check()
        assert page.locator(f'[data-review-cell="{key}"]').inner_text() == expected
    assert page.locator('[data-review-cell="remark"] b').count() == 0
    page.locator('[data-withdrawal-column="reason"]').check()
    assert page.locator('[data-review-cell="reason"]').inner_text() == 'review reason'
    page.locator('[data-withdrawal-column="exchange_value"]').uncheck()
    assert page.locator('[data-review-cell="exchange_value"]').is_hidden()
    page.keyboard.press('Escape')
    assert not page.locator('.withdrawal-columns').evaluate('(e)=>e.open')
    page.locator('#reviewRefresh').click()
    page.wait_for_function("document.querySelector('[data-review-column=reason]')?.hidden === false")
    assert page.locator('[data-review-column="exchange_value"]').is_hidden()
    page.locator('#reviewFilters [type=reset]').click()
    page.wait_for_function("document.querySelector('[data-review-column=reason]')?.hidden === false")
    assert page.locator('[data-review-column="exchange_value"]').is_hidden()
    page.evaluate("reviewStates.withdrawals.page=2;renderReviewPage('withdrawals')")
    assert page.locator('[data-review-column="reason"]').is_visible()
    assert page.locator('[data-review-column="exchange_value"]').is_hidden()
    page.locator('.withdrawal-columns summary').click()
    keys = page.locator('.withdrawal-column-options input:checked').evaluate_all('(els)=>els.map(e=>e.dataset.withdrawalColumn)')
    for key in keys:
        if key != 'reason':
            page.locator(f'[data-withdrawal-column="{key}"]').uncheck()
    assert page.locator('[data-withdrawal-column="reason"]').is_disabled()
    page.locator('#reviewRefresh').click()
    assert page.locator('[data-review-column="reason"]').is_visible()
    page.evaluate("api=async()=>({items:[],total:0});renderReviewPage('withdrawals')")
    assert page.locator('tbody td[colspan]').get_attribute('colspan') == '2'
    assert page.locator('#withdrawalSelectAll').is_disabled()
    assert not errors, errors
    browser.close()
    print('PASS: rejection payloads, blank validation, image rendering, editable invalid filters, stale request isolation (mock data).')
