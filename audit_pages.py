"""Read-only browser audit with named screenshots and explicit failure records."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

routes = ['dashboard','members','agents','games','ads','withdrawals','subsidies','coin-logs','risk-whitelist','risk-history','risk-devices','profile','book']
out = Path('visual-baseline/audit')
out.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1920,'height':1080})
    page.goto('http://127.0.0.1:3000/')
    page.fill('#loginForm [name=username]', '18532306918')
    page.fill('#loginForm [name=password]', '123456')
    page.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    page.locator('.member-filters').wait_for()
    for route in routes:
        errors, failures = [], []
        def on_error(error): errors.append(str(error))
        def on_response(response):
            if response.status >= 400: failures.append({'url':response.url, 'status':response.status})
        page.on('pageerror',on_error)
        page.on('response',on_response)
        entry = {'route':route,'screenshot':route+'.png'}
        try:
            page.goto('http://127.0.0.1:3000/#'+route, wait_until='networkidle')
            page.locator('#content > *').first.wait_for(timeout=10000)
            page.wait_for_function("document.querySelector('#content')?.getAttribute('aria-busy') !== 'true'")
            entry['content_length'] = len(page.locator('#content').inner_text())
            entry['visible_errors'] = [message.strip() for message in page.locator('#content .error-state,#content [role=alert]').all_inner_texts() if message.strip()]
            entry['row_count'] = page.locator('#content tbody tr').count()
            page.screenshot(path=str(out/entry['screenshot']),full_page=True)
        except Exception as error:
            entry['failure'] = str(error).splitlines()[0]
        entry.update(errors=errors,failed_responses=failures)
        entry['load_passed'] = not errors and not failures and not entry.get('visible_errors') and 'failure' not in entry
        results.append(entry)
        page.remove_listener('pageerror',on_error)
        page.remove_listener('response',on_response)
        print(route, 'PASS' if entry['load_passed'] else 'FAIL', flush=True)
    browser.close()
(out/'manifest.json').write_text(json.dumps({'viewport':[1920,1080],'scope':'Page loading only; visual and interaction parity not certified','pages':results},ensure_ascii=False,indent=2),encoding='utf-8')
assert all(entry['load_passed'] for entry in results), [entry for entry in results if not entry['load_passed']]
