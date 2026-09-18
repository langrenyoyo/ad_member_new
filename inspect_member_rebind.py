"""Inspect reference relation editor without submitting business writes or saving member values."""
import json
import os
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    base = 'https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base + '/index/login')
    page.fill('[name=username]', os.environ['PARITY_USERNAME'])
    page.fill('[name=password]', os.environ['PARITY_PASSWORD'])
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="gameuser?ref=addtabs"]').wait_for(state='attached')
    blocked = []
    def readonly(route):
        if route.request.method in ('GET', 'HEAD', 'OPTIONS'):
            route.continue_()
        else:
            blocked.append(route.request.method)
            route.abort()
    page.route('**/*', readonly)
    page.goto(base + '/gameuser', wait_until='networkidle')
    page.locator('#table tbody a[href*="/htedit/"]').first.click()
    frame = page.locator('.layui-layer-iframe').last.frame_locator('iframe')
    frame.locator('body').wait_for()
    page.wait_for_timeout(800)
    result = {
        'scope': 'Read-only form structure; current member values omitted; no save attempted',
        'title': page.locator('.layui-layer-title').last.inner_text(),
        'fields': frame.locator('form .form-group').evaluate_all('''els=>els.map(el=>({label:el.querySelector('label')?.textContent.trim(),
          controls:[...el.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='hidden').map(e=>({tag:e.tagName,type:e.type,name:e.name,
          required:e.required,readonly:e.readOnly,disabled:e.disabled,rule:e.getAttribute('data-rule'),placeholder:e.placeholder,classes:e.className,
          source:e.getAttribute('data-source'),primaryKey:e.getAttribute('data-primary-key'),field:e.getAttribute('data-field')}))}))'''),
        'buttons': frame.locator('button').all_text_contents(),
        'blocked_writes': blocked,
    }
    if not result['fields']:
        result['notice'] = frame.locator('body').inner_text()[:200]
    Path('visual-baseline/reference-verified/member-rebind.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    fixture={'id':9200,'parent_id':11,'ht_id':22,'ht_top_id':33}
    out=Path('visual-baseline/fixtures/member-rebind');out.mkdir(parents=True,exist_ok=True)
    for key,value in fixture.items():
        frame.locator(f'[name="row[{key}]"]').evaluate('(e,v)=>e.value=String(v)',value)
    frame.locator('body').evaluate('()=>document.fonts.ready')
    page.locator('.layui-layer-iframe').last.screenshot(path=str(out/'reference.png'))
    local=browser.new_page(viewport={'width':1920,'height':1080})
    row={**fixture,'username':'fixture-rebind','status':1}
    local.route('**/api/v1/members?*',lambda r:r.fulfill(json={'total':1,'items':[row]}))
    local.route('**/api/v1/members/9200',lambda r:r.fulfill(json=row) if r.request.method=='GET' else r.abort())
    local.goto('http://127.0.0.1:3000/#members')
    local.fill('#loginForm [name=username]',os.environ['PARITY_USERNAME']);local.fill('#loginForm [name=password]',os.environ['PARITY_PASSWORD'])
    local.locator('#loginForm').evaluate('f=>f.requestSubmit()')
    local.locator('[data-member-rebind]').click()
    local.wait_for_function("!document.querySelector('#memberRebindDialog [type=submit]').disabled")
    local.evaluate('document.fonts.ready')
    local.locator('#memberRebindDialog').screenshot(path=str(out/'local.png'))
    a=Image.open(out/'reference.png').convert('RGB');b=Image.open(out/'local.png').convert('RGB')
    assert a.size==b.size,(a.size,b.size)
    diff=ImageChops.difference(a,b);diff.save(out/'diff.png')
    report={'scope':'Relation editor with identical browser fixtures; server relation side effects unverified','mean_rgb':sum(ImageStat.Stat(diff).mean)/3,'changed_pixel_ratio':sum(max(pixel)>10 for pixel in diff.getdata())/(a.width*a.height)}
    (out/'data.json').write_text(json.dumps(fixture,indent=2),encoding='utf-8')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report)
    browser.close()
