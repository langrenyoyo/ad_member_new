"""Capture the reference content document at the local content viewport size."""
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

OUT = Path('visual-baseline/ads-matched')
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php/'
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    local = browser.new_page(viewport={'width':1920, 'height':1080})
    local.goto('http://127.0.0.1:3000/')
    local.fill('[name=username]', '18532306918')
    local.fill('[name=password]', '123456')
    local.locator('#loginForm').evaluate('(f)=>f.requestSubmit()')
    local.locator('.app-shell').wait_for(state='visible')
    local.evaluate("location.hash='#ads'")
    local.locator('.ads-table').wait_for()
    box = local.locator('#content').bounding_box()
    width, height = round(box['width']), 1080-round(box['y'])
    reference = browser.new_page(viewport={'width':width, 'height':height})
    reference.route('**/*', lambda route: route.abort() if route.request.resource_type == 'script' and urlparse(route.request.url).hostname != 'ad.leadink.cn' else route.continue_())
    reference.goto(BASE+'index/login', wait_until='domcontentloaded')
    reference.fill('[name=username]', '18532306918')
    reference.fill('[name=password]', '123456')
    reference.locator('button[type=submit],input[type=submit]').first.click()
    reference.wait_for_timeout(2000)
    reference.goto(BASE+'ad?ref=baseline', wait_until='networkidle')
    (OUT/'reference-body.txt').write_text(reference.locator('body').inner_text(), encoding='utf-8')
    reference.screenshot(path=str(OUT/'reference-diagnostic.png'))
    assert reference.locator('input[type=password]').count() == 0, 'Reference redirected to login'
    assert '观看时间' in reference.locator('body').inner_text(), 'Reference ads page missing'
    reference.screenshot(path=str(OUT/'reference.png'))
    metrics = reference.locator('form input,form select,form button').evaluate_all('(es)=>es.map(e=>({name:e.name,text:e.textContent,value:e.value,box:e.getBoundingClientRect().toJSON()}))')
    local.fill('#watchedRange', '2099-01-01 00:00:00 - 2099-01-01 23:59:59')
    local.locator('#adsFilters').evaluate('(f)=>f.requestSubmit()')
    local.wait_for_timeout(600)
    local.locator('#watchedRange').evaluate('(e)=>e.blur()')
    local.screenshot(path=str(OUT/'local.png'), clip={'x':box['x'],'y':box['y'],'width':width,'height':height})
    (OUT/'manifest.json').write_text(json.dumps({'reference_url':reference.url,'local_url':local.url,'scope':'content only, no header/sidebar','viewport':[width,height],'local_clip':box,'reference_metrics':metrics,'data_state':'local future-date empty results; reference live results; data not normalized'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Captured matched content viewport', width, height)
    browser.close()
