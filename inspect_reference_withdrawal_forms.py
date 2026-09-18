"""Read-only capture of withdrawal edit/reason form structure; no submissions."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(BASE + '/index/login', wait_until='domcontentloaded')
    page.fill('[name=username]', '18532306918')
    page.fill('[name=password]', '123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="tixian?ref=addtabs"]').wait_for(state='attached')
    response = page.request.get(BASE + '/tixian/index', params={'limit':1,'offset':0,'sort':'id','order':'desc','filter':'{}','op':'{}'}, headers={'X-Requested-With':'XMLHttpRequest'})
    data = response.json()
    rows = data.get('rows', [])
    result = {'list_status': response.status, 'total':data.get('total'), 'forms':{}}
    suffix = f"/ids/{rows[0]['id']}" if rows else ''
    for action in (['edit', 'reason'] if rows else ['reason']):
        page.goto(BASE + f'/tixian/{action}' + suffix, wait_until='domcontentloaded')
        result['forms'][action] = page.locator('form').evaluate_all('''forms => forms.map(form => ({
            action: form.getAttribute('action'),
            controls: Array.from(form.querySelectorAll('input,select,textarea,button')).map(e => ({
                tag:e.tagName, type:e.type, name:e.name,
                label:e.closest('.form-group')?.querySelector('label')?.textContent.trim(),
                placeholder:e.placeholder, required:e.required,
                options:e.tagName==='SELECT'?Array.from(e.options).map(o=>({value:o.value,text:o.text})):undefined,
                text:e.tagName==='BUTTON'?e.textContent.trim():undefined
            }))
        }))''')
    output = Path('visual-baseline/reference-verified/withdrawals-forms.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    browser.close()
