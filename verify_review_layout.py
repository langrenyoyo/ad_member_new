"""Compare desktop filter geometry against captured reference DOM rectangles."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.goto('http://127.0.0.1:3010/')
    page.fill('#loginForm [name=username]','18532306918')
    page.fill('#loginForm [name=password]','123456')
    page.locator('#loginForm').evaluate('(form)=>form.requestSubmit()')
    page.locator('.member-filters').wait_for()
    for kind in ['withdrawals','subsidies']:
        page.goto('http://127.0.0.1:3010/#'+kind,wait_until='networkidle')
        page.locator(f'#reviewFilters[data-review-kind="{kind}"]').wait_for()
        reference=json.loads((ROOT/f'visual-baseline/reference-verified/{kind}-layout.json').read_text(encoding='utf-8'))
        current=page.locator('#reviewFilters>label').evaluate_all('(els)=>els.map(e=>({text:e.querySelector("span").textContent,input:e.querySelector("input:not([type=hidden]),select").getBoundingClientRect().toJSON()}))')
        expected=[row for row in reference['form'] if row.get('input')]
        assert len(current)==len(expected)
        differences=[]
        for actual,target in zip(current,expected):
            assert actual['text']==target['text']
            for key,offset in [('x',230),('y',50),('width',0),('height',0)]:
                delta=actual['input'][key]-target['input'][key]-offset
                if abs(delta)>1:differences.append({'field':actual['text'],'dimension':key,'delta':delta})
        print(kind,'geometry differences:',json.dumps(differences,ensure_ascii=True))
        assert not differences,differences
        page.fill('#reviewFilters [name=username]','unsent fixture')
        page.locator('#reviewSearchToggle').click()
        assert page.locator('#reviewFilters').is_hidden()
        assert page.locator('#reviewSearchToggle').get_attribute('aria-expanded')=='false'
        page.locator('#reviewSearchToggle').click()
        assert page.locator('#reviewFilters [name=username]').input_value()=='unsent fixture'
        page.locator('#reviewFilters [type=reset]').click()
        page.wait_for_function("document.querySelector('#reviewFilters [name=username]').value === ''")
        page.screenshot(path=str(ROOT/f'visual-baseline/verified/{kind}-layout.png'))
        print(kind,'geometry and search toggle passed')
    browser.close()
