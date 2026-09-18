"""Read-only reference member creation form structure; no submissions."""
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
    toolbar=page.locator('#toolbar a,#toolbar button').evaluate_all('els=>els.map(e=>({text:e.textContent.trim(),cls:e.className}))')
    add_visible=page.locator('#toolbar .btn-add').count()>0
    page.goto(base+'/gameuser/add',wait_until='networkidle')
    frame=page
    result={'toolbar':toolbar,'add_button_present':add_visible,'title':page.title(),
      'notice':page.locator('body').inner_text()[:200] if page.locator('form').count()==0 else None,
      'tabs':frame.locator('.nav-tabs a').all_text_contents(),
      'fields':frame.locator('form .form-group').evaluate_all('''els=>els.map(el=>({label:el.querySelector('label')?.textContent.trim(),
      controls:[...el.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='hidden').map(e=>({tag:e.tagName,type:e.type,name:e.name,
      required:e.required,rule:e.getAttribute('data-rule'),placeholder:e.placeholder,
      options:e.tagName==='SELECT'?[...e.options].map(o=>({value:o.value,text:o.text})):undefined}))}))''')}
    Path('visual-baseline/reference-verified/member-create-fields.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True));browser.close()
