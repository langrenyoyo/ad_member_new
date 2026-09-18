"""Inspect reference behavior summary controls without invoking mutations."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path('visual-baseline/reference-verified')
base='https://ad.leadink.cn/DmvTqXBpfF.php'
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1536,'height':822})
    page.goto(base+'/index/login')
    page.fill('[name=username]','18532306918');page.fill('[name=password]','123456')
    page.locator('button[type=submit],input[type=submit]').first.click()
    page.wait_for_url(lambda url:'/index/login' not in url)
    response=page.request.get(base+'/gameuser/index',params={'limit':1,'offset':0,'filter':'{}','op':'{}'},headers={'X-Requested-With':'XMLHttpRequest'})
    member=response.json()['rows'][0];uid=member['id']
    page.route('**/*',lambda route:route.abort() if route.request.method not in ('GET','HEAD') or any(action in route.request.url for action in ('imeiidban','deviceidban','/del/','/multi/')) else route.continue_())
    page.goto(base+f'/users/yige/index/user_id/{uid}',wait_until='networkidle')
    info=page.evaluate('''()=>({
      controls:[...document.querySelectorAll('#first a,#first button')].filter(el=>!el.closest('.bootstrap-table')).map(el=>({text:el.textContent.trim(),cls:el.className,
        onclick:el.getAttribute('onclick')?.replace(/(["'])[^"']*\\1/g,"'REDACTED'"),href:el.getAttribute('href')?.replace(/\\d+/g,'ID')})),
      inlineScripts:[...document.scripts].filter(s=>!s.src).map((s,i)=>({i,length:s.textContent.length,functions:[...s.textContent.matchAll(/function\\s+(\\w+)\\s*\\(/g)].map(m=>m[1])})),
      metricElements:[...document.querySelectorAll('#first .row [id]')].map(el=>({tag:el.tagName,id:el.id,cls:el.className})),
      summaryLayout:[...document.querySelectorAll('#first>.row,#first>.row>div,#first>.row>div>div')].map(el=>{const s=getComputedStyle(el);return {tag:el.tagName,cls:el.className,rect:el.getBoundingClientRect().toJSON(),font:s.font,padding:s.padding,margin:s.margin,background:s.background};})
    })''')
    names=[name for script in info['inlineScripts'] for name in script['functions']]
    info['functions']=page.evaluate('names=>Object.fromEntries(names.filter(n=>typeof window[n]==="function").map(n=>[n,window[n].toString()]))',names)
    info['memberKeys']=sorted(member)
    info['jsonFields']={}
    for key,value in member.items():
        if isinstance(value,dict):info['jsonFields'][key]=sorted(value)
        elif isinstance(value,str) and value.startswith('{'):
            try:info['jsonFields'][key]=sorted(json.loads(value))
            except (ValueError,TypeError):pass
    page.locator('#first a.btn-dialog').first.click()
    page.locator('.layui-layer-iframe').last.wait_for()
    page.add_style_tag(content='.layui-layer{animation:none!important}')
    info['appWindow']=page.locator('.layui-layer-iframe').last.evaluate('''el=>({rect:el.getBoundingClientRect().toJSON(),
      title:el.querySelector('.layui-layer-title')?.textContent,
      titleStyle:(()=>{const s=getComputedStyle(el.querySelector('.layui-layer-title'));return {height:s.height,background:s.background,color:s.color,font:s.font};})(),
      controls:[...el.querySelectorAll('.layui-layer-setwin a')].map(node=>node.className)})''')
    page.goto(base+f'/gameuser/userdata/user_id/{uid}',wait_until='networkidle')
    info['appDetails']=page.evaluate('''()=>({
      title:document.title,headers:[...document.querySelectorAll('thead th')].map(el=>el.textContent.trim()),
      fields:[...document.querySelectorAll('form input,form textarea,form select')].map(el=>({tag:el.tagName,name:el.name,type:el.type})),
      labels:[...document.querySelectorAll('form label')].map(el=>el.textContent.trim()),
      tables:[...document.querySelectorAll('table')].map(el=>({id:el.id,cls:el.className,rect:el.getBoundingClientRect().toJSON()})),
      bodyStyle:{padding:getComputedStyle(document.body).padding,background:getComputedStyle(document.body).background},
      rowCount:document.querySelectorAll('tbody tr').length,
      cellStyles:[...document.querySelectorAll('tbody tr:first-child td')].map(el=>{const s=getComputedStyle(el);return {
        length:el.textContent.trim().length,colspan:el.colSpan,font:s.font,padding:s.padding,borderTop:s.borderTop,
        textAlign:s.textAlign,background:s.background};}),
      headerStyles:[...document.querySelectorAll('thead th')].map(el=>{const s=getComputedStyle(el);return {
        text:el.textContent.trim(),font:s.font,padding:s.padding,border:s.border,textAlign:s.textAlign,
        whiteSpace:s.whiteSpace,background:s.background,rect:el.getBoundingClientRect().toJSON()};}),
      scripts:[...document.scripts].filter(s=>s.src).map(s=>s.src)
    })''')
    (out/'member-behavior-device.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print(json.dumps(info,ensure_ascii=True))
