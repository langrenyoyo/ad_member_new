"""Read attachment chooser definitions without saving business values."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080})
    base='https://ad.leadink.cn/DmvTqXBpfF.php'
    page.goto(base+'/index/login')
    page.fill('[name=username]',os.environ['PARITY_USERNAME']);page.fill('[name=password]',os.environ['PARITY_PASSWORD'])
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="gameuser?ref=addtabs"]').wait_for(state='attached')
    page.route('**/*',lambda r:r.continue_() if r.request.method in ('GET','HEAD','OPTIONS') else r.abort())
    page.goto(base+'/gameuser',wait_until='networkidle')
    page.locator('#table tbody input[type=checkbox]').first.check();page.locator('#toolbar .btn-edit').click()
    editor=page.locator('.layui-layer-iframe').last.frame_locator('iframe')
    editor.locator('.fachoose').wait_for();page.wait_for_timeout(600)
    editor.locator('.fachoose').click();page.wait_for_timeout(1200)
    result=[]
    for frame in page.frames:
        if 'attachment' not in frame.url:continue
        frame.wait_for_load_state('networkidle')
        frame.locator('body').wait_for()
        print({'title':frame.title(),'tables':frame.locator('table').count(),'forms':frame.locator('form').count()})
        denied=frame.locator('table,form').count()==0 and '你没有权限访问' in frame.locator('body').inner_text()
        result.append({'path':frame.url.split('?')[0].split('.php')[-1], 'access_denied':denied,
            'headers':frame.locator('thead th').all_text_contents(),
            'buttons':frame.locator('#toolbar button,.fixed-table-toolbar button').evaluate_all('els=>els.map(e=>({text:e.textContent.trim(),title:e.title,name:e.name}))'),
            'inputs':frame.locator('input,select').evaluate_all('els=>els.filter(e=>!e.closest("tbody")).map(e=>({name:e.name,type:e.type,placeholder:e.placeholder,options:e.tagName==="SELECT"?[...e.options].map(o=>({value:o.value,text:o.text})):undefined}))')})
    assert result,'attachment frame not found'
    Path('visual-baseline/reference-verified/member-attachment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True));browser.close()
