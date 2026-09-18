"""Read-only inspection of the agent create form; no form is submitted."""
import ast,json
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE='https://ad.leadink.cn/DmvTqXBpfF.php'
credentials={}
for node in ast.walk(ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1200,'height':900});page.goto(BASE+'/index/login')
    for selector,value in credentials.items():page.fill(selector,value)
    page.locator('button[type=submit],input[type=submit]').first.click();page.wait_for_url(lambda url:'/index/login' not in url)
    result={}
    for path in ['/agent/add','/agent/edit/ids/133']:
        response=page.request.get(BASE+path)
        result[path]={'status':response.status,'url':response.url}
        if response.ok:
            page.goto(BASE+path,wait_until='networkidle')
            result[path].update(page.evaluate('''() => ({
                title: document.title,
                bodyTextLength: document.body.innerText.length,
                bodyTextHead: document.body.innerText.trim().slice(0,240),
                forms: [...document.forms].map(form => ({action: form.action, controlCount: form.querySelectorAll('input,select,textarea,button').length})),
                controls: [...document.querySelectorAll('input,select,textarea,button,a')].slice(0,100).map(e => ({tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',href:e.getAttribute('href')||'',className:e.className||'',text:(e.innerText||e.value||'').trim().slice(0,80)})),
                iframes: [...document.querySelectorAll('iframe')].map(e => ({src:e.src,id:e.id,name:e.name})),
                scripts: [...document.scripts].map(e => e.src).filter(Boolean),
                dialogs: [...document.querySelectorAll('[role=dialog],.layui-layer,.modal')].map(e => ({id:e.id,className:e.className,visible:!!(e.offsetWidth||e.offsetHeight)}))
            })'''))
            result[path]['forms']=page.locator('form').evaluate_all('''forms=>forms.map(form=>({action:form.action,controls:[...form.querySelectorAll('input,select,textarea,button')].map(e=>({tag:e.tagName,type:e.type,name:e.name,value:e.value,required:e.required,placeholder:e.placeholder,label:e.closest('.form-group')?.querySelector('label')?.textContent.trim(),options:e.tagName==='SELECT'?[...e.options].map(o=>({value:o.value,text:o.text})):null,text:e.tagName==='BUTTON'?e.textContent.trim():null}))}))''')
    Path('visual-baseline/reference-verified/agent-create-form.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=True));browser.close()
