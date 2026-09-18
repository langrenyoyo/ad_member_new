"""Read-only aggregate evidence; do not store member accounts or device identifiers."""
import json
from collections import Counter
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(BASE+'/index/login', wait_until='domcontentloaded')
    page.fill('[name=username]', '18532306918')
    page.fill('[name=password]', '123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="risk/userd?ref=addtabs"]').wait_for(state='attached')
    result = {}
    for route in ['risk/userd/index','gameuser/index']:
        response = page.request.get(BASE+'/'+route, params={'limit':200,'offset':0,'sort':'id','order':'desc','filter':'{}','op':'{}'}, headers={'X-Requested-With':'XMLHttpRequest'})
        data = response.json()
        rows = data.get('rows', [])
        result[route] = {'status':response.status,'total':data.get('total'),'sample_count':len(rows),
            'field_names':sorted(set().union(*(row.keys() for row in rows))),
            'device_id_ban_distribution':dict(Counter(str(row.get('device_id_ban','missing')) for row in rows))}
    Path('visual-baseline/reference-verified/device-scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
    browser.close()
