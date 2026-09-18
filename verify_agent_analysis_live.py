"""Read-only smoke check against the running local application."""
import ast
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

credentials={}
for node in ast.walk(ast.parse(Path('inspect_withdrawal_blacklist.py').read_text(encoding='utf-8-sig'))):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='fill' and len(node.args)==2:
        key=ast.literal_eval(node.args[0])
        if key in ('[name=username]','[name=password]'):credentials[key]=ast.literal_eval(node.args[1])
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1920,'height':1080});errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:3000/#agents')
    for selector,value in credentials.items():page.locator('#loginForm '+selector).fill(value)
    page.locator('#loginForm').evaluate('f=>f.requestSubmit()');page.locator('[data-agent-enter]').first.wait_for()
    aid=page.locator('[data-agent-enter]').first.get_attribute('data-agent-enter')
    def readonly(route):
        if route.request.method not in ('GET','HEAD'):route.abort();return
        route.continue_()
    page.route('**/api/**',readonly)
    page.evaluate("id=>{sessionStorage.setItem('agent-dashboard-id',id);location.hash='agent-analysis'}",aid)
    page.wait_for_function('document.querySelectorAll("[data-analysis-chart] canvas").length===6')
    assert page.locator('#agentAnalysisError').inner_text()==''
    assert not errors,errors
    print(json.dumps({'passed':True,'charts':6,'visible_rows':page.locator('#agentAnalysisTable tbody tr').count(),'scope_matches':page.evaluate('id=>agentAnalysisState.scope===Number(id)',aid)}))
    browser.close()
