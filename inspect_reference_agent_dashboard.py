"""Read-only aggregate dashboard structure; omit account and configuration secrets."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1680,'height':1000})
    page.goto(BASE+'/index/login',wait_until='domcontentloaded')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.locator('a[href*="agent?ref=addtabs"]').wait_for(state='attached')
    response=page.request.get(BASE+'/agent/index',params={'limit':1,'offset':0,'filter':'{}','op':'{}'},headers={'X-Requested-With':'XMLHttpRequest'})
    rows=response.json().get('rows',[])
    if not rows:raise RuntimeError('No agent available')
    page.goto(BASE+'/agents/dash/index/agent_id/'+str(rows[0]['id']),wait_until='networkidle')
    data=page.locator('body').evaluate('''body=>({text:body.innerText,links:Array.from(body.querySelectorAll('a[href]')).map(e=>({text:e.textContent.trim(),href:e.getAttribute('href')})),chart:{column:window.Config?.column,userdata:window.Config?.userdata}})''')
    Path('visual-baseline/reference-verified/agent-dashboard.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    page.screenshot(path='visual-baseline/reference-verified/agent-dashboard.png',full_page=True)
    print(json.dumps(data,ensure_ascii=True))
    browser.close()
